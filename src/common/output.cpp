#include "common/output.h"

#include <algorithm>
#include <charconv>
#include <fstream>
#include <stdexcept>
#include <vector>

int64_t totalOccurrences(const IndexParts& parts) {
    int64_t sum = 0;
    for (const Index& idx : parts)
        for (const auto& kv : idx) sum += kv.second.total;
    return sum;
}

static void appendInt(std::string& s, int64_t v) {
    char buf[24];
    auto res = std::to_chars(buf, buf + sizeof(buf), v);
    s.append(buf, res.ptr);
}

void writeIndex(const IndexParts& parts, const std::string& path) {
    std::ofstream out(path, std::ios::binary);
    if (!out) throw std::runtime_error("cannot open " + path);

    // std::string порівнює байти як unsigned char, тобто за кодами UTF-8
    std::vector<const Index::value_type*> rows;
    size_t words = 0;
    for (const Index& idx : parts) words += idx.size();
    rows.reserve(words);
    for (const Index& idx : parts)
        for (const auto& kv : idx) rows.push_back(&kv);
    std::sort(rows.begin(), rows.end(),
              [](const Index::value_type* a, const Index::value_type* b) { return a->first < b->first; });

    constexpr size_t kFlushSize = 1 << 22;
    std::string buf;
    buf.reserve(kFlushSize + (1 << 16));
    std::vector<Posting> ps;

    for (const Index::value_type* row : rows) {
        const Entry& e = row->second;
        ps = e.postings;
        std::sort(ps.begin(), ps.end(), [](const Posting& a, const Posting& b) {
            return a.count != b.count ? a.count > b.count : a.doc < b.doc;
        });

        buf += row->first;
        buf += '\t';
        appendInt(buf, e.total);
        buf += '\t';
        for (size_t i = 0; i < ps.size(); ++i) {
            if (i) buf += ',';
            buf += "doc";
            appendInt(buf, ps[i].doc);
            buf += ':';
            appendInt(buf, ps[i].count);
        }
        buf += '\n';

        if (buf.size() >= kFlushSize) {
            out.write(buf.data(), static_cast<std::streamsize>(buf.size()));
            buf.clear();
        }
    }
    out.write(buf.data(), static_cast<std::streamsize>(buf.size()));
    if (!out) throw std::runtime_error("write failed: " + path);
}
