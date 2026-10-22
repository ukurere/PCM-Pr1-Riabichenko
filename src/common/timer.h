#pragma once

#include <chrono>

class Timer {
public:
    Timer() : start_(std::chrono::steady_clock::now()) {}

    void reset() { start_ = std::chrono::steady_clock::now(); }

    double elapsedMs() const {
        return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start_).count();
    }

private:
    std::chrono::steady_clock::time_point start_;
};
