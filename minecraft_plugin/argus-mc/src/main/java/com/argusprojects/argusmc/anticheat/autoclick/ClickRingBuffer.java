package com.argusprojects.argusmc.anticheat.autoclick;

final class ClickRingBuffer {

    static final int DEFAULT_CAPACITY = 128;

    private final long[] data;
    private int head;
    private int size;

    ClickRingBuffer(int capacity) {
        this.data = new long[Math.max(16, capacity)];
    }

    void push(long value) {
        data[head] = value;
        head = (head + 1) % data.length;
        if (size < data.length) {
            size++;
        }
    }

    int size() {
        return size;
    }

    long getFromNewest(int back) {
        if (back >= size) {
            return 0L;
        }
        int idx = (head - 1 - back) % data.length;
        if (idx < 0) {
            idx += data.length;
        }
        return data[idx];
    }

    int countWithin(long windowMs, long now) {
        int n = 0;
        for (int i = 0; i < size; i++) {
            long t = getFromNewest(i);
            if (now - t > windowMs) {
                break;
            }
            n++;
        }
        return n;
    }

    boolean hasPauseLongerThan(long windowMs, long now, long pauseMs) {
        if (size < 2) {
            return true;
        }
        long oldestInWindow = 0L;
        for (int i = size - 1; i >= 0; i--) {
            long t = getFromNewest(i);
            if (now - t <= windowMs) {
                oldestInWindow = t;
            } else {
                break;
            }
        }
        if (oldestInWindow == 0L) {
            return true;
        }

        long prev = 0L;
        for (int i = 0; i < size; i++) {
            long t = getFromNewest(i);
            if (now - t > windowMs) {
                break;
            }
            if (prev != 0L) {
                long gap = prev - t;
                if (gap >= pauseMs) {
                    return true;
                }
            }
            prev = t;
        }
        return false;
    }

    void clear() {
        head = 0;
        size = 0;
    }
}
