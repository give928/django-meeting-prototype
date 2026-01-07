const meetings = function (options) {
    const MESSAGE_CONFIRM_TRANSCRIPT = '🛠️ 전사 및 교정·요약 작업을 시작할까요?'

    let seconds = 0;
    let timerInterval = null;
    let analyser = null;
    let rafId = null;
    let mediaStream = null;
    let audioCtx = null;
    let mediaRecorder = null;
    let audioChunks = [];
    let lastBlobUrl = null;
    let startPollingInterval = null;
    let isManualSeeking = false;
    let pendingSeekTime = null;

    this.options = Object.assign({
            meetingId: null,
            meetingForm: document.getElementById('meeting-form'),
            startRecodingButton: document.getElementById('startRecodingButton'),
            stopRecodingButton: document.getElementById('stopRecodingButton'),
            uploadButton: document.getElementById('uploadButton'),
            audioFile: document.getElementById('audioFile'),
            uploadFileButton: document.getElementById('uploadFileButton'),
            recordingTimer: document.getElementById('recordingTimer'),
            recordingVolume: document.getElementById('recordingVolume'),
            recordingStatus: document.getElementById('recordingStatus'),
            recordingPlay: document.getElementById('recordingPlay'),
            recordings: document.getElementById('recordings'),
            viewTranscriptButtonClassName: 'viewTranscriptButton',
            pollingTranscriptButtonClassName: 'pollingTranscriptButton',
            requestTranscriptButtonClassName: 'requestTranscriptButton'
        },
        options);


    this.initialize = () => {
        if (this.options.startRecodingButton) {
            this.options.startRecodingButton.addEventListener('click', async (event) => {
                event.preventDefault();

                await this.record();
            });
        }

        if (this.options.stopRecodingButton) {
            this.options.stopRecodingButton.addEventListener('click', (event) => {
                event.preventDefault();

                if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                    mediaRecorder.stop();
                }
            });
        }

        if (this.options.uploadButton) {
            this.options.uploadButton.addEventListener('click', async (event) => {
                event.preventDefault();

                await this.upload();
            });
        }

        if (this.options.audioFile) {
            this.options.audioFile.addEventListener('change', () => {
                this.options.uploadFileButton.disabled = this.options.audioFile.files.length === 0;
            });
        }

        if (this.options.uploadFileButton) {
            this.options.uploadFileButton.addEventListener('click', async (event) => {
                event.preventDefault();

                if (this.options.audioFile.files.length === 0) {
                    return;
                }

                await this.upload(this.options.audioFile.files[0]);
            });
        }

        const viewTranscriptButtons = this.options.recordings.getElementsByClassName(this.options.viewTranscriptButtonClassName);
        for (let i = 0; i < viewTranscriptButtons.length; i++) {
            viewTranscriptButtons[i].addEventListener("click", async (event) => {
                event.preventDefault();

                await this.showTranscript(viewTranscriptButtons[i]);
            });
        }

        const pollingTranscriptButtons = this.options.recordings.getElementsByClassName(this.options.pollingTranscriptButtonClassName);
        for (let i = 0; i < pollingTranscriptButtons.length; i++) {
            pollingTranscriptButtons[i].addEventListener("click", async (event) => {
                event.preventDefault();

                const confirmed = await confirmModal.show({
                    message: MESSAGE_CONFIRM_TRANSCRIPT
                });
                if (confirmed) {
                    await this.transcribe(pollingTranscriptButtons[i]);
                }
            });

            this.checkOngoingTranscription(pollingTranscriptButtons[i].dataset.recording_id);
        }

        const requestTranscriptButtons = this.options.recordings.getElementsByClassName(this.options.requestTranscriptButtonClassName);
        for (let i = 0; i < requestTranscriptButtons.length; i++) {
            requestTranscriptButtons[i].addEventListener("click", async (event) => {
                event.preventDefault();

                const confirmed = await confirmModal.show({
                    message: MESSAGE_CONFIRM_TRANSCRIPT
                });
                if (confirmed) {
                    await this.transcribe(requestTranscriptButtons[i]);
                }
            });
        }

        const audios = this.options.recordings.querySelectorAll('audio');
        audios.forEach(audio => {
            this.bindAudioEvent(audio);
        });
    };

    this.bindAudioEvent = (audio) => {
        if (audio.dataset.bound === 'true') {
            return;
        }
        audio.dataset.bound = 'true';

        audio.addEventListener("canplay", () => {
            if (pendingSeekTime !== null) {
                isManualSeeking = true;
                audio.currentTime = pendingSeekTime;

                pendingSeekTime = null;
            }
        });

        audio.addEventListener("seeking", () => {
            isManualSeeking = true;
        });

        audio.addEventListener("seeked", () => {
            isManualSeeking = false;

            this.onPlayAudio(audio);
        });

        audio.addEventListener("timeupdate", async () => {
            if (isManualSeeking) {
                return;
            }
            await this.onPlayAudio(audio);
        });

        audio.addEventListener('error', async () => {
            try {
                const response = await fetch(audio.currentSrc);
                if (response.status === 401 || response.status === 403) {
                    const data = await response.json();
                    alert(data.message || "🚫 로그인 후 이용해 주세요.");
                    window.location.href = `/sign-in/?next=${window.location.pathname}`;
                }
            } catch (e) {
                toast('😱 오디오 재생에 실패했어요.\n관리자에게 문의해 주세요.');
            }
        });
    };

    this.startTimer = () => {
        seconds = 0;
        this.options.recordingTimer.textContent = "00:00:00";
        timerInterval = setInterval(() => {
            seconds++;
            const h = String(Math.floor(seconds / 3600)).padStart(2, '0');
            const m = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0');
            const s = String(seconds % 60).padStart(2, '0');
            this.options.recordingTimer.textContent = `${h}:${m}:${s}`;
        }, 1000);
    };

    this.stopTimer = () => {
        clearInterval(timerInterval);
        timerInterval = null;
    }

    this.visualizeMicrophoneVolume = () => {
        if (!analyser) return;
        const bufferLength = analyser.fftSize;
        const dataArray = new Uint8Array(bufferLength);
        analyser.getByteTimeDomainData(dataArray);

        // RMS 계산(음량)
        let sumSquares = 0;
        for (let i = 0; i < bufferLength; i++) {
            const v = (dataArray[i] - 128) / 128;
            sumSquares += v * v;
        }
        const rms = Math.sqrt(sumSquares / bufferLength);
        const level = Math.min(rms * 3, 1); // 0..1

        // draw
        const ctx = this.options.recordingVolume.getContext('2d');
        ctx.clearRect(0, 0, this.options.recordingVolume.width, this.options.recordingVolume.height);
        const w = this.options.recordingVolume.width * level;
        const grd = ctx.createLinearGradient(0, 0, this.options.recordingVolume.width, 0);
        grd.addColorStop(0, '#28a745');
        grd.addColorStop(1, '#ffc107');
        ctx.fillStyle = grd;
        ctx.fillRect(0, 0, w, this.options.recordingVolume.height);

        // loop
        rafId = requestAnimationFrame(this.visualizeMicrophoneVolume);
    };

    this.ensureStream = async () => {
        if (mediaStream) {
            return mediaStream;
        }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            toast('🚫️ 현재 브라우저는 녹음을 지원하지 않아요.');
            throw new Error('no getUserMedia');
        }
        try {
            const stream = await navigator.mediaDevices.getUserMedia({audio: true});
            mediaStream = stream;
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            analyser = audioCtx.createAnalyser();
            analyser.fftSize = 2048;
            const source = audioCtx.createMediaStreamSource(stream);
            source.connect(analyser);
            return stream;
        } catch (err) {
            toast('🎤 브라우저 마이크 권한을 부여하고 다시 시도해 주세요.');
            throw err;
        }
    };

    this.record = async () => {
        try {
            const stream = await this.ensureStream();
            audioChunks = [];
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.ondataavailable = e => {
                if (e.data && e.data.size > 0) {
                    audioChunks.push(e.data);
                }
            };
            mediaRecorder.onstop = this.stop;

            mediaRecorder.start();
            this.options.recordingStatus.classList.remove('visually-hidden');
            this.options.startRecodingButton.classList.add('d-none');
            this.options.stopRecodingButton.classList.remove('d-none');
            this.options.uploadButton.classList.add('d-none');

            this.visualizeMicrophoneVolume();
            this.startTimer();
        } catch (err) {
            toast('😱 녹음 중 예외가 발생했어요.\n관리자에게 문의해 주세요.');
        }
    };

    this.stop = () => {
        this.options.recordingStatus.classList.add('visually-hidden');
        cancelAnimationFrame(rafId);
        rafId = null;
        this.stopTimer();

        const blob = new Blob(audioChunks, {type: 'audio/webm'});
        const url = URL.createObjectURL(blob);
        lastBlobUrl = url;

        const item = document.createElement('div');
        item.className = "recording-item card p-3 mb-2 shadow-sm";

        const row = document.createElement('div');
        row.className = "d-flex align-items-center";

        const audio = document.createElement('audio');
        audio.controls = true;
        audio.src = url;
        audio.className = "flex-grow-1";

        const download = document.createElement('a');
        download.href = url;
        download.download = `record-${Date.now()}.webm`;
        download.className = 'btn btn-outline-secondary btn-sm ms-3 align-self-center';
        download.textContent = '다운로드';

        row.appendChild(audio);
        row.appendChild(download);

        item.appendChild(row);

        this.options.recordingPlay.innerHTML = '';
        this.options.recordingPlay.prepend(item);

        this.options.uploadButton.classList.remove('d-none');

        this.options.stopRecodingButton.classList.add('d-none');
        this.options.startRecodingButton.classList.remove('d-none');
    };

    this.upload = async (audioFile = null) => {
        if (this.options.meetingId === null) {
            const validation = FormValidators.validate(this.options.meetingForm);
            if (!validation) {
                return false;
            }
        }

        const confirmed = await confirmModal.show({
            message: '🛠️ 선택하신 파일을 업로드 후 전사 및 교정·요약 작업을 시작할까요?'
        });
        if (!confirmed) {
            return;
        }

        if (this.options.meetingId === null) {
            const created = await this.createMeeting();
            if (!created) {
                return;
            }
        }

        let blobOrFile;
        let filename;

        if (audioFile === null) {
            if (!lastBlobUrl) {
                return alert('업로드할 녹음이 없어요.');
            }
            blobOrFile = new Blob(audioChunks, {type: 'audio/webm'});
            filename = `record-${Date.now()}.webm`;
        } else {
            blobOrFile = audioFile;
            filename = audioFile.name;
        }

        const formData = new FormData();
        formData.append('file', blobOrFile, filename);

        if (audioFile !== null) {
            formData.append('source_type', 'upload_file');
        } else {
            formData.append('source_type', 'browser_recording');
        }

        try {
            showSpinner();

            this.options.uploadButton.disabled = true;
            this.options.uploadButton.textContent = '업로드 중...';
            this.options.uploadFileButton.disabled = true;
            this.options.uploadFileButton.textContent = '업로드 중...';

            const response = await fetch(`/meetings/${this.options.meetingId}/recordings/`, {
                method: 'POST',
                body: formData,
                headers: {
                    'Accept': 'application/json',
                    'X-CSRFToken': document.getElementsByName('csrfmiddlewaretoken')[0].value
                }
            });
            const data = await response.json();

            if (data.status === 'success') {
                this.options.audioFile.value = null;

                await this.addRecording(data);

                this.resetRecordingState();
            } else {
                hideSpinner();
                toast(data.message || data.error || '😱 녹음 파일 업로드 중 예외가 발생했어요.');
            }
        } catch (err) {
            hideSpinner();
            toast('😱 녹음 파일 업로드를 실패했어요.\n관리자에게 문의해 주세요.');
            this.options.uploadButton.disabled = false;
            this.options.uploadButton.textContent = '서버 업로드';
        } finally {
            this.options.uploadButton.disabled = false;
            this.options.uploadButton.textContent = '업로드';
            this.options.uploadFileButton.disabled = false;
            this.options.uploadFileButton.textContent = '업로드';
        }
    };

    this.createMeeting = async () => {
        try {
            const formData = new FormData(this.options.meetingForm);

            const response = await fetch(`/meetings/0/`, {
                method: 'POST',
                body: formData,
                headers: {
                    'Accept': 'application/json',
                    'X-CSRFToken': document.getElementsByName('csrfmiddlewaretoken')[0].value
                }
            });

            const data = await response.json();

            if (data.status === 'success') {
                this.options.meetingId = data.meeting_id;
                window.history.replaceState({meetingId: data.meeting_id}, '', `/meetings/${data.meeting_id}/`);
                return true;
            } else {
                toast(data.message || '😱 회의 등록에 실패했어요.');
            }
        } catch (err) {
            toast('😱 회의 등록 중 시스템 예외가 발생했어요.');
        }
        return false;
    };

    this.resetRecordingState = () => {
        seconds = 0;
        lastBlobUrl = null;
        audioChunks = [];

        this.options.recordingTimer.textContent = '00:00:00';

        const ctx = this.options.recordingVolume.getContext('2d');
        ctx.clearRect(0, 0, this.options.recordingVolume.width, this.options.recordingVolume.height);

        this.options.recordingStatus.classList.add('visually-hidden');
        this.options.uploadButton.classList.add('d-none');
        this.options.startRecodingButton.classList.remove('d-none');
        this.options.stopRecodingButton.classList.add('d-none');
        this.options.recordingPlay.innerHTML = '';

        hideSpinner();
    };

    this.addRecording = async (data) => {
        const item = document.createElement('div');
        item.className = "accordion-item";
        item.id = `meeting-recording-${data.id}`;
        this.options.recordings.appendChild(item);
        const nodata = this.options.recordings.parentElement.querySelector('.nodata');
        if (nodata) {
            nodata.classList.add('d-none');
        }
        if (this.options.recordings.classList.contains('d-none')) {
            this.options.recordings.classList.remove('d-none');
        }
        item.innerHTML = `
                <h4 class="accordion-header">
                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-recording-${data.id}" aria-expanded="false"
                            aria-controls="collapse-recording-${data.id}">${this.options.recordings.children.length}. ${this.ms_to_hms(data.play_millisecond)}</button>
                </h4>
                <div id="collapse-recording-${data.id}" class="accordion-collapse collapse">
                    <div class="accordion-body">
                        <div class="d-flex align-items-center">
                            <audio data-recording_id="${data.id}" controls src="${data.download_url}?mode=play" class="flex-grow-1"></audio>
                            <a href="${data.download_url}" download class="btn btn-outline-secondary btn-sm ms-3">다운로드</a>
                            <button class="btn btn-warning btn-sm ms-2 ${this.options.requestTranscriptButtonClassName} disabled" data-recording_id="${data.id}">전사 처리</button>
                        </div>
                        <div class="transcript-container mt-2 rounded d-none" id="transcript-${data.id}">
                            <div data-bs-spy="scroll" data-bs-offset="0" class="position-relative overflow-auto scrollspy-transcript" id="transcript-content-${data.id}">
                                <div class="spinner-border text-primary d-none" id="spinner-${data.id}"></div>
                                <span></span>
                            </div>
                        </div>
                    </div>
                </div>`;

        const requestTranscriptButton = item.querySelector(`.${this.options.requestTranscriptButtonClassName}`);
        requestTranscriptButton.addEventListener('click', (event) => {
            event.preventDefault();

            this.transcribe(requestTranscriptButton.dataset.recording_id);
        });

        await this.transcribe(requestTranscriptButton);

        const newAudio = item.querySelector('audio');
        if (newAudio) {
            this.bindAudioEvent(newAudio);
        }
    };

    this.transcribe = async (button) => {
        const recordingId = button.dataset.recording_id;

        const container = document.getElementById(`transcript-${recordingId}`);
        container.classList.remove("d-none");

        try {
            const response = await fetch(`/meetings/${this.options.meetingId}/recordings/${recordingId}/`, {
                method: 'PUT',
                headers: {
                    'Accept': 'application/json',
                    'X-CSRFToken': document.getElementsByName('csrfmiddlewaretoken')[0].value
                }
            });
            const data = await response.json();

            if (data.status === 'waiting' || data.status === 'processing') {
                BootstrapAccordionUtils.focus(document.getElementById(`collapse-recording-${recordingId}`), 'center');
                toast(data.message || '🛠️ 전사 작업을 시작할게요.', 'info');
                this.startPolling(recordingId, data.task_id);
            } else if (data.status === 'completed') {
                BootstrapAccordionUtils.focus(document.getElementById(`collapse-recording-${recordingId}`), 'center');
                toast('🔎 전사 기록을 불러올게요.', 'info');
                this.updateTranscriptButton(recordingId, data.id);
                const viewButton = button.cloneNode(false);
                viewButton.classList.remove(this.options.requestTranscriptButtonClassName);
                viewButton.classList.remove(this.options.pollingTranscriptButtonClassName);
                viewButton.classList.add(this.options.viewTranscriptButtonClassName);
                viewButton.addEventListener('click', async (event) => {
                    event.preventDefault();

                    await this.showTranscript(viewTranscriptButtons[i]);
                });
                const parent = button.parentElement;
                parent.removeChild(button);
                parent.appendChild(viewButton);
                await this.showTranscript(viewButton);
            } else {
                toast(data.message || data.error || '😱 전사 처리 중 예외가 발생했어요.', 'error');
                container.classList.add("d-none");
            }
        } catch (err) {
            toast('😱 음성 텍스트 변환에 실패했어요.');
            container.classList.add("d-none");
        } finally {
            hideSpinner();
        }
    };

    this.updateTranscriptButton = (recordingId, speechRecognitionId, summarizationId) => {
        const oldButton = document.querySelector(`button[data-recording_id="${recordingId}"].${this.options.requestTranscriptButtonClassName}, .${this.options.pollingTranscriptButtonClassName}`);

        if (!oldButton) return;

        const viewTranscriptButton = document.createElement('button');
        viewTranscriptButton.classList.add('btn', 'btn-primary', 'btn-sm', 'ms-2', this.options.viewTranscriptButtonClassName);
        viewTranscriptButton.dataset.recording_id = recordingId;
        viewTranscriptButton.dataset.speech_recognition_id = speechRecognitionId;
        viewTranscriptButton.dataset.summarization_id = summarizationId;
        viewTranscriptButton.innerHTML = '전사 보기';
        viewTranscriptButton.addEventListener("click", async (event) => {
            event.preventDefault();
            await this.showTranscript(viewTranscriptButton);
        });

        oldButton.parentElement.appendChild(viewTranscriptButton);
        oldButton.remove();
    };

    this.showTranscriptByButton = async (recordingId, transcriptId, summarizationId) => {
        const element = {
            dataset: {
                recording_id: recordingId,
                transcript_id: transcriptId,
                summarization_id: summarizationId
            }
        };
        await this.showTranscript(element);
    };

    this.checkOngoingTranscription = async (recordingId) => {
        try {
            const response = await fetch(`/meetings/${this.options.meetingId}/recordings/${recordingId}/`, {
                method: 'PUT',
                headers: {
                    'Accept': 'application/json',
                    'X-CSRFToken': document.getElementsByName('csrfmiddlewaretoken')[0].value
                }
            });
            const data = await response.json();

            if ((data.status === 'waiting' || data.status === 'processing') && data.task_id) {
                toast('🔎 백그라운드에서 진행 중인 전사 작업을 감지했어요. 상태 확인을 시작할게요.', 'info');
                this.startPolling(recordingId, data.task_id);
            } else if (data.status === 'completed') {
                this.updateTranscriptButton(recordingId, data.id);
            } else {
                toast('😱 전사 상태 확인에 실패했어요.\n관리자에게 문의해 주세요.');
            }
        } catch (err) {
            toast('😱 전사 상태 확인에 실패했어요.\n관리자에게 문의해 주세요.');
        }
        BootstrapAccordionUtils.focus(document.getElementById(`collapse-recording-${recordingId}`), 'center');
    };

    this.startPolling = (recordingId, taskId) => {
        if (startPollingInterval !== null) {
            clearInterval(startPollingInterval);
        }
        const container = document.getElementById(`transcript-${recordingId}`);
        const spinner = document.getElementById(`spinner-${recordingId}`);
        const content = document.getElementById(`transcript-content-${recordingId}`);

        let statusDiv = document.getElementById(`transcript-status-${recordingId}`);
        let statusSpan = document.getElementById(`transcript-status-message-${recordingId}`);
        if (!statusDiv) {
            statusDiv = document.createElement('div');
            statusDiv.id = `transcript-status-${recordingId}`;
            content.prepend(statusDiv);
        }
        if (!statusSpan) {
            statusSpan = document.createElement('span');
            statusSpan.id = `transcript-status-message-${recordingId}`;
            statusSpan.className = `ms-3`;
            statusDiv.prepend(statusSpan);
        }

        container.classList.remove("d-none");
        spinner.classList.remove("d-none");
        content.innerHTML = '';
        statusDiv.appendChild(spinner);
        statusDiv.appendChild(statusSpan);
        content.appendChild(statusDiv);

        statusDiv.className = 'alert alert-info mt-3 mb-0 d-flex align-items-center';
        statusSpan.innerHTML = '🛠 전사 작업을 처리하고 있어요.';

        startPollingInterval = setInterval(async () => {
                try {
                    const statusResponse = await fetch(`/meetings/${this.options.meetingId}/recordings/${recordingId}/tasks/${taskId}/`, {
                        method: 'GET',
                        headers: {
                            'Accept': 'application/json',
                            'X-CSRFToken': document.getElementsByName('csrfmiddlewaretoken')[0].value
                        }
                    });
                    const data = await statusResponse.json();

                    statusSpan.innerHTML = `${data.message}`;

                    if (data.status === 'completed') {
                        clearInterval(startPollingInterval);
                        spinner.classList.add("d-none");
                        statusDiv.className = 'alert alert-success mt-3 mb-0';

                        toast(data.message, 'success');

                        this.updateTranscriptButton(recordingId, data.speech_recognition_id, data.summarization_id);
                        await this.showTranscriptByButton(recordingId, data.speech_recognition_id, data.summarization_id);
                    } else if (data.status === 'error' || data.status === 'failed') {
                        clearInterval(startPollingInterval);
                        spinner.classList.add("d-none");
                        statusDiv.className = 'alert alert-danger mt-3 mb-0';
                        toast(data.message, 'error');
                    }
                } catch (err) {
                    clearInterval(startPollingInterval);
                    spinner.classList.add("d-none");
                    statusDiv.className = 'alert alert-danger mt-3 mb-0';
                    statusSpan.textContent = '😱 상태 확인 중 네트워크 문제가 발생했어요.';
                }
            },
            5000
        );
    };

    this.showTranscript = async (element) => {
        const recordingId = element.dataset.recording_id;
        const summarizationId = element.dataset.summarization_id;
        if (typeof summarizationId === 'undefined' || summarizationId === '') {
            this.checkOngoingTranscription(recordingId);
            return;
        }
        const transcriptContainer = document.getElementById(`transcript-${recordingId}`);
        const contentContainer = document.getElementById(`transcript-content-${recordingId}`);
        const spinnerContainer = document.getElementById(`spinner-${recordingId}`);

        if (contentContainer.dataset.loaded === 'true') {
            BootstrapAccordionUtils.focus(document.getElementById(`collapse-recording-${recordingId}`));
            return;
        }
        transcriptContainer.classList.remove("d-none");
        contentContainer.innerHTML = "";
        spinnerContainer.classList.remove("d-none");

        try {
            const response = await fetch(
                `/meetings/${this.options.meetingId}/recordings/${recordingId}/`, {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json',
                        'X-CSRFToken': document.getElementsByName('csrfmiddlewaretoken')[0].value
                    }
                });

            const data = await response.json();
            spinnerContainer.classList.add("d-none");

            if (data.status !== "success") {
                contentContainer.innerHTML = `<div class="alert alert-danger mt-3 mb-0 d-flex align-items-center" role="alert">😱 전사 데이터를 불러오지 못했어요: ${data.message}</div>`;
                return;
            }

            let transcriptHtml = `
                <div class="mt-3">
                    <table class="table table-hover">
                        <tbody>
                        <tr>
                            <th scope="col">음성 인식 모델</th>
                            <th scope="col">정렬 모델</th>
                            <th scope="col">화자 분리 모델</th>
                            <th scope="col">언어 코드</th>
                            <th scope="col">교정·요약 생성형 AI 모델</th>
                        </tr>
                        <tr>
                            <td>${data.info.speech_recognition_model_name}</td>
                            <td>${data.info.align_model_name}</td>
                            <td>${data.info.diarization_model_name}</td>
                            <td>${data.info.language_code !== null ? data.info.language_code : '확인 중'}</td>
                            <td>${data.info.generative_ai_model_name}</td>
                        </tr>
                        </tbody>
                    </table>
                </div>`;

            transcriptHtml += `
                <div class="nav nav-tabs flex-grow-1 mt-3" id="nav-tab-${data.recording_id}" role="tablist">
                    <button class="nav-link active" id="nav-summarization-tab-${data.recording_id}" data-bs-toggle="tab" data-bs-target="#nav-summarization-${data.recording_id}" type="button" role="tab"
                            aria-controls="nav-summarization-${data.recording_id}" aria-selected="true">요약
                    </button>
                    <button class="nav-link" id="nav-meeting-minutes-tab-${data.recording_id}" data-bs-toggle="tab" data-bs-target="#nav-meeting-minutes-${data.recording_id}" type="button" role="tab"
                            aria-controls="nav-meeting-minutes-${data.recording_id}" aria-selected="false">회의록
                    </button>
                    <button class="nav-link" id="nav-action-items-tab-${data.recording_id}" data-bs-toggle="tab" data-bs-target="#nav-action-items-${data.recording_id}" type="button" role="tab"
                            aria-controls="nav-action-items-${data.recording_id}" aria-selected="false">액션 아이템
                    </button>
                    <button class="nav-link" id="nav-corrections-tab-${data.recording_id}" data-bs-toggle="tab" data-bs-target="#nav-corrections-${data.recording_id}" type="button"
                            role="tab" aria-controls="nav-corrections-${data.recording_id}" aria-selected="false">교정
                    </button>
                    <button class="nav-link" id="nav-segments-tab-${data.recording_id}" data-bs-toggle="tab" data-bs-target="#nav-segments-${data.recording_id}" type="button"
                            role="tab" aria-controls="nav-segments-${data.recording_id}" aria-selected="false">원본
                    </button>
                </div>`;

            let summarizationHtml = '';
            let meetingMinutesHtml = '';
            let actionItemsHtml = '';
            let correctionsHtml = '';
            let segmentsHtml = '';
            if (data.segments && data.segments.length > 0) {
                summarizationHtml = this.escapeHtml(data.summarization_content);
                meetingMinutesHtml = marked.parse(data.minutes_content);
                correctionsHtml += `<div class="chat-container">`;
                segmentsHtml += `<div class="chat-container">`;

                const speakerColorMap = {};
                let colorIndex = 0;

                data.segments.forEach((segment, index) => {
                    if (!(segment.speaker in speakerColorMap)) {
                        speakerColorMap[segment.speaker] = colorIndex % 6;
                        colorIndex++;
                    }
                    const themeClass = `speaker-theme-${speakerColorMap[segment.speaker]}`;

                    const timeRange = `${this.formatMs(segment.start)} ~ ${this.formatMs(segment.end)}`;

                    correctionsHtml += `
                        <div class="d-flex transcript-segment ${themeClass}${index === 0 ? '' : ' mt-2'}" data-start="${segment.start}" data-end="${segment.end}">
                            <div class="flex-grow-1" style="min-width: 0;">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="fw-bold">${this.escapeHtml(segment.speaker)}</span>
                                    <span class="text-secondary small me-1"><i class="bi bi-clock me-1"></i>${timeRange}</span>
                                </div>
                                <div class="chat-bubble text-break text-pre-wrap">${this.escapeHtml(segment.corrected_text)}</div>
                            </div>
                        </div>`;

                    segmentsHtml += `
                        <div class="d-flex transcript-segment ${themeClass}${index === 0 ? '' : ' mt-2'}" data-start="${segment.start}" data-end="${segment.end}">
                            <div class="flex-grow-1" style="min-width: 0;">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="fw-bold">${this.escapeHtml(segment.speaker)}</span>
                                    <span class="text-secondary small me-1"><i class="bi bi-clock me-1"></i>${timeRange}</span>
                                </div>
                                <div class="chat-bubble text-break text-pre-wrap">${this.escapeHtml(segment.text)}</div>
                            </div>
                        </div>`;
                });

                correctionsHtml += `</div>`;
                segmentsHtml += `</div>`;
            } else {
                summarizationHtml = '<div class="text-center text-muted py-4"><i class="bi bi-chat-square-dots fs-1 d-block mb-2"></i>🚫️ 요약된 내용이 없어요.</div>';
                meetingMinutesHtml = '<div class="text-center text-muted py-4"><i class="bi bi-chat-square-dots fs-1 d-block mb-2"></i>🚫️ 회의록이 없어요.</div>';
                correctionsHtml = '<div class="text-center text-muted py-4"><i class="bi bi-chat-square-dots fs-1 d-block mb-2"></i>🚫️ 교정된 대화 내용이 없어요.</div>';
                segmentsHtml = '<div class="text-center text-muted py-4"><i class="bi bi-chat-square-dots fs-1 d-block mb-2"></i>🚫️ 전사된 대화 내용이 없어요.</div>';
            }
            if (data.action_items != null && data.action_items.length > 0) {
                let actionItemsMarkdown = '';
                data.action_items.forEach((item, index) => {
                    if (index > 0) {
                        actionItemsMarkdown += '\n';
                    }
                    actionItemsMarkdown += `${index + 1}. ${item}`;
                });
                actionItemsHtml = marked.parse(actionItemsMarkdown);
            } else {
                actionItemsHtml = '<div class="text-center text-muted py-4"><i class="bi bi-chat-square-dots fs-1 d-block mb-2"></i>🚫 도출된 액션 아이템이 없어요.</div>';
            }

            transcriptHtml += `
                <div class="tab-content" id="nav-tabContent">
                    <div class="tab-pane fade text-pre-wrap active show" id="nav-summarization-${data.recording_id}" role="tabpanel" aria-labelledby="nav-summarization-tab">${summarizationHtml}</div>
                    <div class="tab-pane fade" id="nav-meeting-minutes-${data.recording_id}" role="tabpanel" aria-labelledby="nav-meeting-minutes-tab">${meetingMinutesHtml}</div>
                    <div class="tab-pane fade" id="nav-action-items-${data.recording_id}" role="tabpanel" aria-labelledby="nav-action-items-tab">${actionItemsHtml}</div>
                    <div class="tab-pane nav-corrections fade" id="nav-corrections-${data.recording_id}" role="tabpanel" aria-labelledby="nav-corrections-tab">${correctionsHtml}</div>
                    <div class="tab-pane nav-segments fade" id="nav-segments-${data.recording_id}" role="tabpanel" aria-labelledby="nav-segments-tab">${segmentsHtml}</div>
                </div>`;

            contentContainer.innerHTML = transcriptHtml;
            contentContainer.dataset.loaded = "true";


            const audio = document.querySelector(`#collapse-recording-${recordingId} audio`);
            if (!audio) {
                toast("😱 해당 녹음의 audio 태그를 찾을 수 없어요.");
                return;
            }

            const segments = contentContainer.querySelectorAll(".transcript-segment");
            segments.forEach(segment => {
                segment.addEventListener('click', () => {
                    const startTimeMs = parseInt(segment.dataset.start, 10);
                    const targetTimeSeconds = startTimeMs / 1000;
                    this.seekAudio(audio, targetTimeSeconds);
                });
            });

            BootstrapAccordionUtils.focus(document.getElementById(`collapse-recording-${recordingId}`), 'center');
        } catch (err) {
            spinnerContainer.classList.add("d-none");
            contentContainer.innerHTML = `<div class="alert alert-danger mt-3 mb-0" role="alert">😱 오류가 발생했어요. 관리자에게 문의해 주세요.</div>`;
        }
    };

    this.seekAudio = (audio, targetTimeSeconds) => {
        try {
            audio.currentTime = targetTimeSeconds;
        } catch (e) {
            // iOS (Safari)의 경우 재생 상태에서만 시킹이 허용되는 경우가 존재해서 재생 후 재시도
            console.error("Error setting currentTime:", e);
            if (audio.paused) {
                audio.play()
                    .then(() => {
                        audio.currentTime = targetTimeSeconds;
                        audio.pause()
                    })
                    .catch(e => console.error("Forcing play failed:", e));
            }
        }
    };

    this.onPlayAudio = async (audio) => {
        const currentTimeMs = Math.floor(audio.currentTime * 1000);
        const recordingId = audio.dataset.recording_id;

        if (audio.dataset.loaded_transcript !== 'true') {
            const recordingId = audio.dataset.recording_id;
            const viewTranscriptButton = document.querySelector(`#recording-${recordingId} .${this.options.viewTranscriptButtonClassName}`);
            const navTabContainer = document.getElementById(`nav-tab-${recordingId}`);
            if (viewTranscriptButton && navTabContainer == null && !isManualSeeking) {
                await this.showTranscript(viewTranscriptButton);
                audio.dataset.loaded_transcript = 'true';
            }
        }

        const correctionTab = document.getElementById(`nav-corrections-tab-${recordingId}`);
        const segmentsTab = document.getElementById(`nav-segments-tab-${recordingId}`);
        if (!correctionTab.classList.contains('active') && !segmentsTab.classList.contains('active')) {
            const tab = bootstrap.Tab.getOrCreateInstance(correctionTab);
            tab.show();
        }

        this.highlightSegment(currentTimeMs, recordingId);
    };

    this.highlightSegment = (currentTimeMs, recordingId) => {
        const contentContainer = document.getElementById(`transcript-content-${recordingId}`);
        if (!contentContainer) {
            return;
        }

        const corrections = contentContainer.querySelectorAll('.nav-corrections .transcript-segment');
        const segments = contentContainer.querySelectorAll('.nav-segments .transcript-segment');
        let foundIndex = -1;

        segments.forEach((segment, index) => {
            const start = parseInt(segment.dataset.start, 10);
            const end = parseInt(segment.dataset.end, 10);

            if (currentTimeMs >= start && currentTimeMs < end) {
                foundIndex = index;
            }

            segment.classList.remove('highlight');
            if (corrections[index]) corrections[index].classList.remove('highlight');
        });

        if (foundIndex !== -1) {
            const activeSegment = segments[foundIndex];
            const activeCorrection = corrections[foundIndex];

            activeSegment.classList.add('highlight');
            if (activeCorrection) activeCorrection.classList.add('highlight');

            const targetElement = (activeCorrection && activeCorrection.offsetParent) ? activeCorrection : activeSegment;

            if (targetElement && targetElement.offsetParent) {
                const scrollContainer = contentContainer;

                const elementTop = targetElement.offsetTop;
                const containerHeight = scrollContainer.clientHeight;

                const targetScrollTop = elementTop - (containerHeight / 3);

                scrollContainer.scrollTo({
                    top: targetScrollTop,
                    behavior: 'smooth'
                });
            }
        }
    };

    this.formatMs = (ms) => {
        const totalSeconds = Math.floor(ms / 1000);
        const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
        const seconds = String(totalSeconds % 60).padStart(2, '0');
        return `${minutes}:${seconds}`;
    };

    this.ms_to_hms = (ms) => {
        try {
            if (!ms || ms <= 0) {
                return "00:00:00";
            }

            ms = parseInt(ms, 10);
            const totalSeconds = Math.floor(ms / 1000);

            const hours = Math.floor(totalSeconds / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            const seconds = totalSeconds % 60;

            return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
        } catch (e) {
            return "00:00:00";
        }
    }

    this.escapeHtml = (text) => {
        return text ? text.replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": "&#39;"}[c])) : '';
    };

    this.initialize();
};