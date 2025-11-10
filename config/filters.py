import logging


class IgnoreNoiseRequestsFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        ignore_patterns = [
            '/favicon.ico',
            '/robots.txt',
            '/apple-touch-icon',
            '/.well-known/',
            '/browserconfig.xml',
            '/manifest.json',
        ]
        return not any(p in msg for p in ignore_patterns)
