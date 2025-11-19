#pragma once
#include <cstdint>

namespace sim::setup {

enum class EccType {
    None,
    BCH,
    LDPC
};

enum class MappingGranularity {
    Block,
    Page,
    SubPage
};

} // namespace sim::setup
