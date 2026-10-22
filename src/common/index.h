#pragma once

#include <algorithm>
#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

// Кількість входжень слова в один документ
struct Posting {
    int32_t doc;
    int32_t count;
};

// Запис індексу для одного слова
struct Entry {
    int64_t total = 0;              // загальна кількість входжень
    std::vector<Posting> postings;  // упорядковано за зростанням doc
};

// Зворотний індекс: слово -> запис
using Index = std::unordered_map<std::string, Entry>;

// Індекс, поділений на частини з неперетинними множинами слів (шарди V3).
// Решта версій повертають одну частину.
using IndexParts = std::vector<Index>;

inline IndexParts singlePart(Index&& idx) {
    IndexParts parts;
    parts.push_back(std::move(idx));
    return parts;
}

// Одна операція оновлення індексу: +1 входження слова в документ doc.
// Документи видаються потокам за зростанням номера, тому майже завжди
// запис потрапляє в кінець; бінарний пошук потрібен, лише коли кілька
// потоків одночасно обробляють різні документи.
inline void addOccurrence(Entry& e, int32_t doc) {
    ++e.total;
    std::vector<Posting>& ps = e.postings;
    if (ps.empty() || ps.back().doc < doc) {
        ps.push_back({doc, 1});
        return;
    }
    if (ps.back().doc == doc) {
        ++ps.back().count;
        return;
    }
    auto it = std::lower_bound(ps.begin(), ps.end(), doc,
                               [](const Posting& p, int32_t d) { return p.doc < d; });
    if (it != ps.end() && it->doc == doc) ++it->count;
    else ps.insert(it, {doc, 1});
}

// Сума total по всіх словах (для перевірки V1)
int64_t totalOccurrences(const IndexParts& parts);
