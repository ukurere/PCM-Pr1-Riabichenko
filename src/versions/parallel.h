#pragma once

#include <atomic>
#include <cstddef>
#include <thread>
#include <vector>

#include "common/corpus.h"

// Запускає P потоків; кожен по черзі бере наступний документ (за зростанням номера)
// і викликає work(document, threadId). Розподіл — за файлами, динамічний:
// єдина спільна змінна — атомарний лічильник наступного документа.
template <class F>
void forEachDocumentParallel(const Corpus& corpus, int threads, F&& work) {
    std::atomic<size_t> next{0};
    auto worker = [&](int tid) {
        for (size_t i = next.fetch_add(1, std::memory_order_relaxed); i < corpus.docs.size();
             i = next.fetch_add(1, std::memory_order_relaxed)) {
            work(corpus.docs[i], tid);
        }
    };
    std::vector<std::thread> pool;
    pool.reserve(threads);
    for (int t = 0; t < threads; ++t) pool.emplace_back(worker, t);
    for (std::thread& th : pool) th.join();
}
