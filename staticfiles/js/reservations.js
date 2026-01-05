const reservation = function (options) {
    this.startDate = new Date();
    this.endDate = new Date();
    this.timeSlotCount = 0;
    this.timeSlotWidthPercent = 0;
    this.selectedTimeSlots = new Set();
    this.timeSlots = [];
    this.departemtns = null;
    this.roomId = null;

    this.options = Object.assign({
            readonly: true,
            moveViewPage: true,
            reservationId: null,
            timelineContainer: document.getElementById('timeline'),
            timeRuler: document.getElementById('time-ruler'),
            room: document.getElementById('id_room'),
            startDateTime: null,
            endDateTime: null,
            hierarchicalDepartmentsConfig: null,
            querystring: null,
        },
        options);

    this.initialize = () => {
        if (this.options.readonly === false) {
            const _self = this;
            this.options.room.addEventListener('focus', function() {
                _self.roomId = this.value;
            });
            this.options.room.addEventListener('change', (event) => {
                if (!this.validateAttendees(this.departemtns.getCheckedCount())) {
                    for (let i = 0; i < this.options.room.options.length; i++) {
                        if (this.options.room.options[i].value === this.roomId) {
                            this.options.room.options[i].selected = true;
                            return false;
                        }
                    }
                    return false;
                }
                this.fetchSchedules();
            });
            if (this.options.startDateTime !== null) {
                this.options.startDateTime.addEventListener('change', this.fetchSchedules);
            }
            if (this.options.endDateTime !== null) {
                this.options.endDateTime.addEventListener('change', this.fetchSchedules);
            }
        }
        if (this.options.hierarchicalDepartmentsConfig) {
            this.options.hierarchicalDepartmentsConfig.checkValidator = this.validateAttendees;
            this.departemtns = new tree(this.options.hierarchicalDepartmentsConfig);
        }
        if (this.options.room.value !== '') {
            this.fetchSchedules();
        }
    };

    this.validateAttendees = (count) => {
        const selectedOption = this.options.room.options[this.options.room.selectedIndex];
        const seatCount = parseInt(selectedOption.dataset.seat || "0", 10);
        const capacityCount = parseInt(selectedOption.dataset.capacity || "0", 10);
        if (count > capacityCount) {
            toast(`회의실 최대 수용 인원은 ${capacityCount}명입니다.`);
            return false;
        }
        if (count > seatCount) {
            toast(`회의실 좌석은 ${seatCount}석입니다.`);
            return false;
        }
        return true;
    };

    this.fetchSchedules = () => {
        if (!this.validateFetchSchedule()) {
            return;
        }

        if (this.options.readonly === false) {
            showSpinner();
        }

        const startDatetime = this.options.startDateTime ? (this.options.startDateTime.value + (this.options.startDateTime.value.length === 10 ? 'T09:00' : '')) : '';
        const endDatetime = this.options.endDateTime ? (this.options.endDateTime.value + (this.options.endDateTime.value.length === 10 ? 'T09:00' : '')) : '';
        fetch(`/reservations/schedules/${this.options.room.value}/?readonly=${this.options.readonly}&reservation_id=${this.options.reservationId === null ? '' : this.options.reservationId}&start=${startDatetime}&end=${endDatetime}`, {
            headers: {
                'Content-Type': 'application/json; charset=utf-8'
            }
        })
        .then(response => {
            if (response.status === 401) {
                alert('🚫 로그인 후 이용해 주세요.');
                window.location.href = `/sign-in/?next=${window.location.pathname}`;
                return;
            }
            return response.json()
        })
        .then(json => {
            if (json.start && json.end && json.timelines) {
                this.renderTimeRuler(json.start, json.end);
                const renderedTimeline = this.renderTimeline(json.timelines);
                if (renderedTimeline) {
                    this.updateDatetimeValue(json.status !== 'success');
                }
            }
            if (json.message || json.status !== 'success') {
                toast(json.message ? json.message : '😱 시스템 예외가 발생했어요.');
            }
        }).finally(() => {
            if (this.options.readonly === false) {
                hideSpinner();
            }
        });
    };

    this.validateFetchSchedule = () => {
        if (!this.options.room.value) {
            this.clearTimeRuler();
            this.clearTimeline();
            return false;
        }
        if (this.options.startDateTime && this.options.endDateTime && this.options.startDateTime.value && this.options.endDateTime.value && this.options.startDateTime.value > this.options.endDateTime.value) {
            this.updateDatetimeValue();
            toast('⛔️ 종료 일시는 시작 일시보다 이후여야 해요.');
            return false;
        }

        return true;
    };

    this.clearTimeRuler = () => {
        this.options.timeRuler.innerHTML = '';
    }

    this.renderTimeRuler = (start_datetime, end_datetime) => {
        this.clearTimeRuler();

        this.startDate = new Date(start_datetime);
        this.endDate = new Date(end_datetime);
        this.timeSlotCount = (this.endDate - this.startDate) / 1000 / 60 / 30;
        if (this.timeSlotCount > 96) {
            return false;
        }
        this.timeSlotWidthPercent = 100 / this.timeSlotCount;

        const date = new Date(this.startDate);
        while (date <= this.endDate) {
            const div = document.createElement('div');
            div.style.flex = '1';
            div.style.position = 'relative';
            div.style.borderBottom = '1px solid #eee';
            if (date.getMinutes() === 0) {
                if (date.getHours() === 0) {
                    div.appendChild(this.createDateLabel(date));
                }
                div.appendChild(this.createTimeLabel(date));
            }
            this.options.timeRuler.appendChild(div);

            date.setMinutes(date.getMinutes() + 30);
        }

        return true;
    };

    this.createDateLabel = (date) => {
        const label = document.createElement('span');
        label.style.position = 'absolute';
        label.style.top = '-5em';
        label.style.left = '0';
        label.style.fontSize = '0.7rem';
        label.style.whiteSpace = 'nowrap';
        label.textContent = `${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
        return label;
    };

    this.createTimeLabel = (date) => {
        const label = document.createElement('span');
        label.style.position = 'absolute';
        label.style.top = '-1.2em';
        label.style.left = '0';
        label.style.fontSize = '0.7rem';
        label.style.whiteSpace = 'nowrap';
        label.textContent = `${String(date.getHours()).padStart(2, '0')}:00`;
        return label;
    };

    this.createText = (text) => {
        const div = document.createElement('div');
        div.style.flex = '1';
        div.style.position = 'relative';
        div.classList.add('d-flex');
        div.classList.add('align-items-center');
        div.classList.add('justify-content-center');
        div.classList.add('h-100');
        div.innerText = text;
        return div;
    };

    this.clearTimeline = () => {
        this.options.timelineContainer.innerHTML = '';
        this.selectedTimeSlots.clear();
    };

    this.renderTimeline = (reservations) => {
        this.clearTimeline();

        if (this.timeSlotCount > 96) {
            this.options.timelineContainer.appendChild(this.createText('🚫 2일 이상인 경우 타임라인이 표시되지 않아요.'));
            return false;
        }

        this.timeSlots = Array(this.timeSlotCount).fill({
            status: 'available',
            width: this.timeSlotWidthPercent
        });

        reservations.forEach(reservation => {
            if (reservation.status === 'reserved') {
                const startSlot = Math.floor(reservation.start_offset / 30);
                const endSlot = Math.ceil(reservation.end_offset / 30);
                for (let i = startSlot; i < endSlot; i++) {
                    this.timeSlots[i] = {
                        status: reservation.status,
                        id: reservation.id,
                        time: reservation.time,
                        title: reservation.title || '예약됨',
                        user: reservation.user || '',
                        readonly: reservation.readonly,
                        width: Math.max(startSlot, 0) === i ? this.timeSlotWidthPercent * (Math.min(this.timeSlots.length, endSlot) - Math.max(startSlot, 0)) : 0
                    };
                }
            }
            if (reservation.status === 'selected') {
                const startSlot = Math.floor(reservation.start_offset / 30);
                const endSlot = Math.ceil(reservation.end_offset / 30);
                for (let i = startSlot; i < endSlot; i++) {
                    this.timeSlots[i] = {
                        status: reservation.status,
                        title: reservation.title || '예약됨',
                        user: reservation.user || '',
                        width: this.options.readonly ? (Math.max(startSlot, 0) === i ? this.timeSlotWidthPercent * (Math.min(this.timeSlots.length, endSlot) - Math.max(startSlot, 0)) : 0) : this.timeSlotWidthPercent
                    };
                }
            }
        });

        this.timeSlotColorClasses = [
            'bg-primary',
            'bg-success',
            'bg-danger',
            'bg-warning',
            'bg-info'
        ];
        this.timeSlotColorIndex = Math.floor(Math.random() * this.timeSlotColorClasses.length);

        this.timeSlots.forEach((slot, i) => {
            const div = document.createElement('div');
            div.classList.add('time-slot', 'border-start', 'bg-gradient');
            div.dataset.index = `${i}`;
            if (slot.width === 0) {
                div.style.display = 'none';
            } else {
                div.style.display = '';
                div.style.left = `${i * this.timeSlotWidthPercent}%`;
                div.style.width = `${slot.width}%`;
                div.style.height = '100%';
                div.style.position = 'absolute';
                div.style.top = '0';
                div.style.transition = 'background-color 0.15s, opacity 0.15s';

                if (slot.status === 'reserved') {
                    if (this.options.moveViewPage) {
                        if (slot.readonly === true) {
                            div.classList.add('bg-secondary');
                        } else {
                            div.classList.add(this.timeSlotColorClasses[this.timeSlotColorIndex++ % this.timeSlotColorClasses.length]);
                        }
                        div.style.cursor = 'pointer';
                        div.addEventListener('click', () => {
                            window.location.href = `/reservations/${slot.id}/${this.options.querystring !== null && this.options.querystring !== '' ? '?' + this.options.querystring : ''}`;
                        });
                    } else {
                        div.classList.add('bg-secondary');
                        div.style.cursor = 'not-allowed';
                        div.style.opacity = '0.7';
                    }

                    div.setAttribute('data-bs-toggle', 'tooltip');
                    div.setAttribute('data-bs-html', 'true');
                    div.setAttribute('data-bs-title', `<div class="text-start"><p class="m-0">시간: ${slot.time}</p><p class="m-0">회의: ${slot.title}</p><p class="m-0">예약: ${slot.user}</p></div>`);
                } else {
                    div.style.opacity = '0.3';
                    if (this.options.readonly === false) {
                        div.style.cursor = 'pointer';
                        div.addEventListener('mouseenter', () => {
                            if (!this.selectedTimeSlots.has(i)) {
                                div.style.opacity = '0.6';
                            }
                        });
                        div.addEventListener('mouseleave', () => {
                            if (!this.selectedTimeSlots.has(i)) {
                                div.style.opacity = '0.3';
                            }
                        });
                        div.addEventListener('click', () => this.handleSlotClick(i));
                    }
                }
            }

            this.options.timelineContainer.appendChild(div);

            if (slot.status === 'selected') {
                this.updateTimeSlot(i)
            }
        });

        const tooltipTriggerList = this.options.timelineContainer.querySelectorAll('[data-bs-toggle="tooltip"]');
        [...tooltipTriggerList].forEach(el => new bootstrap.Tooltip(el));

        return true;
    };

    this.handleSlotClick = (index) => {
        if (!this.updateTimeSlot(index)) {
            return;
        }

        const fetch = this.updateDatetimeValue();

        if (fetch) {
            this.fetchSchedules();
        }
    };

    this.updateTimeSlot = (index) => {
        if (this.timeSlots[index].status === 'reserved') {
            toast('🚫 이 시간에는 이미 다른 예약이 있어요.\n다른 시간으로 선택해 주세요.');
            return false;
        }

        if (this.selectedTimeSlots.has(index)) {
            const size = this.selectedTimeSlots.size;
            this.selectedTimeSlots.clear();
            if (size !== 1) {
                this.selectedTimeSlots.add(index);
            }
        } else {
            if (this.selectedTimeSlots.size === 0) {
                this.selectedTimeSlots.add(index);
            } else {
                const sortedSelectedTimeSlots = Array.from(this.selectedTimeSlots).sort((a, b) => a - b);
                const startIndex = sortedSelectedTimeSlots[0];
                const endIndex = sortedSelectedTimeSlots[sortedSelectedTimeSlots.length - 1];

                let selectable = true;
                for (let i = Math.min(startIndex, index); i <= Math.max(endIndex, index); i++) {
                    if (this.timeSlots[i].status === 'reserved') {
                        this.selectedTimeSlots.clear();
                        this.selectedTimeSlots.add(index);
                        selectable = false;
                        break;
                    }
                }

                if (selectable) {
                    for (let i = Math.min(startIndex, index); i <= Math.max(endIndex, index); i++) {
                        this.selectedTimeSlots.add(i);
                    }
                }
            }
        }

        this.updateTimeSlotColors();

        return true;
    };

    this.updateTimeSlotColors = () => {
        const slotElements = this.options.timelineContainer.querySelectorAll('.time-slot');
        slotElements.forEach((el, i) => {
            el.classList.remove('bg-primary', 'bg-secondary');
            el.style.opacity = '0.3';

            const slot = this.timeSlots[i];
            if (slot.status === 'reserved') {
                el.classList.add('bg-secondary');
                el.style.opacity = '0.7';
            } else if (this.selectedTimeSlots.has(i)) {
                el.classList.add('bg-primary');
                el.style.opacity = '0.85';
            }
        });
    };

    this.updateDatetimeValue = () => {
        if (this.options.readonly) {
            return false;
        }
        if (this.options.startDateTime === null || this.options.endDateTime === null) {
            return false;
        }
        if (this.selectedTimeSlots.size === 0) {
            this.options.startDateTime.value = '';
            this.options.endDateTime.value = '';
            return false;
        }

        const sortedTimeSlots = Array.from(this.selectedTimeSlots).sort((a, b) => a - b);
        const startIdx = sortedTimeSlots[0];
        const endIdx = sortedTimeSlots[sortedTimeSlots.length - 1];
        let startHour = this.startDate.getHours() + Math.floor((startIdx * 30) / 60);
        let startDateAdd = 0;
        while (startHour >= 24) {
            startHour -= 24;
            startDateAdd += 1;
        }
        const startDate = new Date(this.startDate);
        startDate.setDate(startDate.getDate() + startDateAdd);
        const startMin = (startIdx * 30) % 60;
        let endHour = this.startDate.getHours() + Math.floor(((endIdx + 1) * 30) / 60);
        let endDateAdd = 0;
        while (endHour >= 24) {
            endHour -= 24;
            endDateAdd += 1;
        }
        const endDate = new Date(this.startDate);
        endDate.setDate(endDate.getDate() + endDateAdd);
        const endMin = ((endIdx + 1) * 30) % 60;

        const endTime = `${String(endHour).padStart(2, '0')}:${String(endMin).padStart(2, '0')}`;

        this.options.startDateTime.value = `${this.formatDate(startDate)}T${String(startHour).padStart(2, '0')}:${String(startMin).padStart(2, '0')}`;
        this.options.endDateTime.value = `${this.formatDate(endDate)}T${endTime}`;

        return true;
    };

    this.formatDate = (d) => {
        return `${d.getFullYear()}-${(d.getMonth() + 1).toString().padStart(2, '0')}-${d.getDate().toString().padStart(2, '0')}`;
    };

    this.initialize();
};