#pragma once

#include <string>

#include "common/index.h"

// Записує індекс у файл у форматі
//   слово<TAB>загальна_кількість<TAB>doc17:12,doc3:5,...
// Рядки — за словом (байти UTF-8); записи — за спаданням кількості,
// за однакової кількості — за зростанням номера документа.
// Частини індексу мають неперетинні множини слів.
void writeIndex(const IndexParts& parts, const std::string& path);
