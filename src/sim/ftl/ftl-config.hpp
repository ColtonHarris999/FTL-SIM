#pragma once

#include <cstdint>
#include <cstddef>

namespace sim::ftl {

// Physical page address – opaque for now.
// Later you can encode (channel, die, plane, block, page) into this.
using Ppa = std::uint64_t;

// Allocate a large block of virtual memory for big tables.
void* mmap_large(std::size_t bytes);

// Free memory allocated by mmap_large.
void mmap_free(void* ptr, std::size_t bytes);

} // namespace sim::ftl
