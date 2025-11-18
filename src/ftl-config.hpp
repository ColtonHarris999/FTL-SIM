#pragma once

#include <cstdint>
#include <cstddef>
#include <stdexcept>
#include <algorithm>
#include <iostream>

#ifdef _WIN32
// ---------- Windows headers ----------
#include <windows.h>
#else
// ---------- POSIX headers ----------
#include <sys/mman.h>
#include <unistd.h>
#endif


// ---------- ECC and Mapping Types ----------

enum class EccType {
    None,
    BCH,
    LDPC,
};

enum class MappingGranularity {
    Block,    // one mapping entry per block
    Page,     // one mapping entry per physical page
    SubPage,  // multiple mapping entries per page (e.g. 4 per page)
};

// Just treat PPA as a 64-bit opaque identifier.
// You can later encode (channel, die, plane, block, page) into this.
using Ppa = std::uint64_t;

// ---------- Helper: mmap for big/sparse tables ----------

// ============================================================
// Cross-platform mmap_large()
// Allocates a large block of virtual address space.
//
// POSIX → mmap()
// Windows → VirtualAlloc()
// ============================================================
inline void* mmap_large(std::size_t bytes) {
#ifdef _WIN32
    // Windows VirtualAlloc equivalent to mmap with no reservation
    void* ptr = VirtualAlloc(
        nullptr,
        bytes,
        MEM_RESERVE | MEM_COMMIT,   // reserve + commit
        PAGE_READWRITE
    );

    if (!ptr) {
        throw std::runtime_error("VirtualAlloc failed");
    }

    return ptr;

#else
    // POSIX mmap
    void* ptr = mmap(nullptr, bytes,
                     PROT_READ | PROT_WRITE,
                     MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE,
                     -1, 0);

    if (ptr == MAP_FAILED) {
        throw std::runtime_error("mmap failed");
    }

    return ptr;
#endif
}

// ---------- User-facing configuration ----------

struct SsdConfig {
    // Physical NAND parameters
    std::uint32_t bits_per_cell;     // e.g., 1(SLC), 2(MLC), 3(TLC), 4(QLC)
    std::uint32_t cells_per_page;    // cells per physical page
    std::uint32_t pages_per_block;   // NAND pages per block

    // Higher-level array geometry
    std::uint32_t blocks_per_plane;
    std::uint32_t planes_per_die;
    std::uint32_t dies_per_package;
    std::uint32_t packages;          // "packages" or "channels" * packages – you can refine later

    // ECC
    EccType ecc_type;
    std::uint32_t ecc_bits_per_1k;   // overhead bits per 1 KiB of user data

    // DRAM model
    std::uint64_t dram_bytes;        // total DRAM available for controller
    std::uint64_t fast_ftl_bytes;    // DRAM reserved for fast FTL (hybrid)

    // FTL mapping
    MappingGranularity base_mapping; // coarse mapping table
    MappingGranularity fast_mapping; // fine mapping in "fast FTL"
    std::uint32_t subpages_per_page; // only used if SubPage, e.g., 4
};
