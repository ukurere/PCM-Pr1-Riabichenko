// Дослідження хибного розділення (окрема програма, не пов'язана з індексом).
// Кожен із P потоків виконує ITERS інкрементів власного елемента спільного масиву.
// Синхронізації немає, гонок даних немає: кожен потік звертається лише до свого елемента.
//
//   A — елементи розміщено послідовно:             int64_t counters[P]
//   B — кожен елемент в окремому рядку кешу:        struct Padded { int64_t value; char pad[56]; }
//   --pad N — довільний заповнювач (0, 8, 24, 32, 56) для контрольного питання 7.
//
// int64_t замість long: у Windows long має 4 байти, і Padded мав би 60 байтів.
// Лічильник читається й записується через volatile, інакше за -O2 компілятор
// згорнув би цикл в одне додавання і звернень до пам'яті не було б.
//
// Один прогін триває лише десятки мілісекунд, тому спершу виконується попередній
// прогін (процесор виходить на робочу частоту), а потім --reps вимірюваних.
//
// Запуск: false_sharing --threads 4 --impl A|B [--pad N] [--iters 10000000] [--reps 5]
//         false_sharing --info        (розмір рядка кешу)

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

namespace {

constexpr int kMaxThreads = 64;

template <size_t Pad>
struct Slot {
    int64_t value;
    char pad[Pad];
};

template <>
struct Slot<0> {
    int64_t value;
};

using CounterA = Slot<0>;   // реалізація A
using PaddedB = Slot<56>;   // реалізація B
static_assert(sizeof(CounterA) == 8, "A: elements must be contiguous");
static_assert(sizeof(PaddedB) == 64, "B: element must occupy one 64-byte cache line");

// Розмір рядка кешу даних L1 за даними ОС
int cacheLineSize() {
#ifdef _WIN32
    DWORD len = 0;
    GetLogicalProcessorInformation(nullptr, &len);
    std::vector<SYSTEM_LOGICAL_PROCESSOR_INFORMATION> info(len / sizeof(SYSTEM_LOGICAL_PROCESSOR_INFORMATION));
    if (!GetLogicalProcessorInformation(info.data(), &len)) return -1;
    for (const auto& i : info) {
        if (i.Relationship == RelationCache && i.Cache.Level == 1 && i.Cache.Type == CacheData) {
            return i.Cache.LineSize;
        }
    }
    return -1;
#else
    return static_cast<int>(sysconf(_SC_LEVEL1_DCACHE_LINESIZE));
#endif
}

// Розміри й кількість кешів усіх рівнів (лише Windows), напр. "L1d=48KBx4 L2=1280KBx4"
std::string cacheSummary() {
#ifdef _WIN32
    DWORD len = 0;
    GetLogicalProcessorInformation(nullptr, &len);
    std::vector<SYSTEM_LOGICAL_PROCESSOR_INFORMATION> info(len / sizeof(SYSTEM_LOGICAL_PROCESSOR_INFORMATION));
    if (!GetLogicalProcessorInformation(info.data(), &len)) return "";
    std::string out;
    for (int level = 1; level <= 3; ++level) {
        for (PROCESSOR_CACHE_TYPE type : {CacheData, CacheInstruction, CacheUnified}) {
            int count = 0;
            DWORD size = 0;
            for (const auto& i : info) {
                if (i.Relationship == RelationCache && i.Cache.Level == level && i.Cache.Type == type) {
                    ++count;
                    size = i.Cache.Size;
                }
            }
            if (!count) continue;
            const char* suffix = type == CacheData ? "d" : type == CacheInstruction ? "i" : "";
            out += " L" + std::to_string(level) + suffix + "=" + std::to_string(size / 1024) + "KBx" +
                   std::to_string(count);
        }
    }
    return out;
#else
    return "";
#endif
}

// Запускає P потоків одночасно й повертає час (мс) від старту до завершення всіх
template <size_t Pad>
double run(int threads, int64_t iters) {
    alignas(64) static Slot<Pad> slots[kMaxThreads];
    for (auto& s : slots) s.value = 0;

    std::atomic<int> ready{0};
    std::atomic<bool> go{false};
    std::vector<std::thread> pool;
    for (int t = 0; t < threads; ++t) {
        pool.emplace_back([&ready, &go, t, iters] {
            volatile int64_t* v = &slots[t].value;
            // Адреса фіксується в регістрі, щоб усі реалізації мали однаковий цикл
            // (для 8-байтових елементів компілятор інакше обирає адресацію база+індекс*8,
            // яка на цьому процесорі сама по собі в кілька разів повільніша).
            asm volatile("" : "+r"(v));
            // Локальна копія: інакше компілятор перечитує iters із пам'яті на кожній
            // ітерації (запис через volatile int64_t* міг би його змінити), і це
            // зайве звернення спотворює вимірювання.
            const int64_t n = iters;
            ready.fetch_add(1);
            while (!go.load(std::memory_order_acquire)) {
            }
            for (int64_t i = 0; i < n; ++i) *v = *v + 1;
        });
    }
    while (ready.load() < threads) {
    }
    auto start = std::chrono::steady_clock::now();
    go.store(true, std::memory_order_release);
    for (std::thread& th : pool) th.join();
    double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - start).count();

    for (int t = 0; t < threads; ++t) {
        if (slots[t].value != iters) {
            std::cerr << "error: counter " << t << " = " << slots[t].value << "\n";
            std::exit(1);
        }
    }
    return ms;
}

double runPad(int pad, int threads, int64_t iters) {
    switch (pad) {
        case 0: return run<0>(threads, iters);
        case 8: return run<8>(threads, iters);
        case 24: return run<24>(threads, iters);
        case 32: return run<32>(threads, iters);
        case 56: return run<56>(threads, iters);
        default: return -1;
    }
}

[[noreturn]] void usage() {
    std::cerr << "Usage: false_sharing --threads P --impl A|B [--pad 0|8|24|32|56] [--iters N] [--reps R]\n"
                 "       false_sharing --info\n";
    std::exit(2);
}

}  // namespace

int main(int argc, char** argv) {
    int threads = 1;
    int pad = -1;
    int reps = 5;
    int64_t iters = 10'000'000;
    std::string impl;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--info") {
            std::cout << "cache_line_bytes=" << cacheLineSize()
                      << " hardware_threads=" << std::thread::hardware_concurrency() << cacheSummary() << "\n";
            return 0;
        }
        if (i + 1 >= argc) usage();
        std::string v = argv[++i];
        if (a == "--threads") threads = std::atoi(v.c_str());
        else if (a == "--impl") impl = v;
        else if (a == "--pad") pad = std::atoi(v.c_str());
        else if (a == "--iters") iters = std::atoll(v.c_str());
        else if (a == "--reps") reps = std::atoi(v.c_str());
        else usage();
    }
    if (threads < 1 || threads > kMaxThreads || iters < 1 || reps < 1) usage();
    if (pad < 0) {
        if (impl == "A") pad = 0;
        else if (impl == "B") pad = 56;
        else usage();
    } else if (impl.empty()) {
        impl = "pad";
    }

    if (runPad(pad, threads, iters) < 0) usage();  // попередній прогін
    for (int r = 0; r < reps; ++r) {
        std::cout << "impl=" << impl << " threads=" << threads << " pad=" << pad
                  << " element_bytes=" << 8 + pad << " iters=" << iters << " rep=" << r
                  << " time_ms=" << runPad(pad, threads, iters) << "\n";
    }
    return 0;
}
