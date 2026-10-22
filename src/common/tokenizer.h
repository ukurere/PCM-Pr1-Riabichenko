#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

#include "common/unicode_tables.h"

// Правила нормалізації (однакові для всіх версій):
//  1. текст у кодуванні UTF-8;
//  2. символи переводяться в нижній регістр;
//  3. роздільник — будь-який символ, що не є літерою (Unicode L*) або цифрою (Nd);
//  4. токени довжиною менше 3 символів (кодових точок) відкидаються.
// Некоректні послідовності UTF-8 вважаються роздільниками.

constexpr size_t kMinTokenLength = 3;

namespace detail {

// Декодує один символ UTF-8 (з перевіркою надлишкових кодувань і сурогатів).
// Повертає кількість байтів або 0, якщо послідовність некоректна.
inline size_t decodeUtf8(const unsigned char* p, const unsigned char* end, uint32_t& cp) {
    const unsigned char b0 = p[0];
    auto cont = [&](size_t i, unsigned char lo = 0x80, unsigned char hi = 0xBF) {
        return p + i < end && p[i] >= lo && p[i] <= hi;
    };
    if (b0 >= 0xC2 && b0 <= 0xDF) {
        if (!cont(1)) return 0;
        cp = ((b0 & 0x1Fu) << 6) | (p[1] & 0x3Fu);
        return 2;
    }
    if (b0 >= 0xE0 && b0 <= 0xEF) {
        const unsigned char lo = b0 == 0xE0 ? 0xA0 : 0x80;
        const unsigned char hi = b0 == 0xED ? 0x9F : 0xBF;
        if (!cont(1, lo, hi) || !cont(2)) return 0;
        cp = ((b0 & 0x0Fu) << 12) | ((p[1] & 0x3Fu) << 6) | (p[2] & 0x3Fu);
        return 3;
    }
    if (b0 >= 0xF0 && b0 <= 0xF4) {
        const unsigned char lo = b0 == 0xF0 ? 0x90 : 0x80;
        const unsigned char hi = b0 == 0xF4 ? 0x8F : 0xBF;
        if (!cont(1, lo, hi) || !cont(2) || !cont(3)) return 0;
        cp = ((b0 & 0x07u) << 18) | ((p[1] & 0x3Fu) << 12) | ((p[2] & 0x3Fu) << 6) | (p[3] & 0x3Fu);
        return 4;
    }
    return 0;
}

inline void appendUtf8(std::string& s, uint32_t cp) {
    if (cp < 0x80) {
        s += static_cast<char>(cp);
    } else if (cp < 0x800) {
        s += static_cast<char>(0xC0 | (cp >> 6));
        s += static_cast<char>(0x80 | (cp & 0x3F));
    } else if (cp < 0x10000) {
        s += static_cast<char>(0xE0 | (cp >> 12));
        s += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
        s += static_cast<char>(0x80 | (cp & 0x3F));
    } else {
        s += static_cast<char>(0xF0 | (cp >> 18));
        s += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
        s += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
        s += static_cast<char>(0x80 | (cp & 0x3F));
    }
}

}  // namespace detail

// Викликає onToken(const std::string&) для кожного токена тексту в порядку появи.
template <class F>
void forEachToken(const std::string& text, F&& onToken) {
    std::string token;
    size_t length = 0;  // довжина токена в кодових точках
    auto flush = [&] {
        if (length >= kMinTokenLength) onToken(token);
        token.clear();
        length = 0;
    };

    const unsigned char* p = reinterpret_cast<const unsigned char*>(text.data());
    const unsigned char* end = p + text.size();
    while (p < end) {
        uint32_t cp;
        if (*p < 0x80) {
            cp = *p++;
        } else if (size_t n = detail::decodeUtf8(p, end, cp)) {
            p += n;
        } else {
            ++p;
            flush();
            continue;
        }
        if (uni::isAlnum(cp)) {
            detail::appendUtf8(token, uni::toLower(cp));
            ++length;
        } else {
            flush();
        }
    }
    flush();
}
