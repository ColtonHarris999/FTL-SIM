#pragma once
#include "ftl_geometry.hpp"

// How many logical units exist for a given mapping granularity?
inline std::uint64_t units_for_granularity(
    MappingGranularity gran,
    const SsdGeometry& geom,
    std::uint32_t subpages_per_page
) {
    switch (gran) {
        case MappingGranularity::Block:
            return geom.blocks_total;
        case MappingGranularity::Page:
            return geom.pages_total;
        case MappingGranularity::SubPage:
            if (subpages_per_page == 0) {
                throw std::invalid_argument("SubPage mapping requires subpages_per_page > 0");
            }
            return geom.pages_total * static_cast<std::uint64_t>(subpages_per_page);
        default:
            throw std::invalid_argument("Unknown MappingGranularity");
    }
}

// ftl_layout.hpp (continued)

struct FtlLayout {
    SsdConfig  cfg;
    SsdGeometry geom;

    // -------- Base (slow) mapping table --------
    std::uint64_t base_entries;        // total logical units at base granularity
    std::size_t   base_bytes;          // total bytes of base mapping table
    Ppa*          base_table;          // mmap'd region

    // -------- Fast (DRAM) mapping table --------
    std::uint64_t fast_entries_requested;  // how many units exist at fast granularity
    std::uint64_t fast_entries_allocated;  // how many we can fit in fast_ftl_bytes
    std::size_t   fast_bytes;              // bytes actually allocated
    Ppa*          fast_table;              // DRAM allocation (new[])

    // Derived coverage
    double fast_coverage_fraction;     // fraction of fast-address space covered

    FtlLayout(const SsdConfig& c)
        : cfg(c),
          geom(derive_geometry(c)),
          base_entries(0),
          base_bytes(0),
          base_table(nullptr),
          fast_entries_requested(0),
          fast_entries_allocated(0),
          fast_bytes(0),
          fast_table(nullptr),
          fast_coverage_fraction(0.0)
    {
        if (cfg.fast_ftl_bytes > cfg.dram_bytes) {
            throw std::invalid_argument("fast_ftl_bytes cannot exceed dram_bytes");
        }

        const std::size_t entry_size = sizeof(Ppa);

        // ---- BASE MAPPING TABLE (coarse) ----
        base_entries = units_for_granularity(
            cfg.base_mapping,
            geom,
            cfg.subpages_per_page
        );
        base_bytes = base_entries * entry_size;

        // Allocate with mmap so we can go into the multi-GB range safely
        base_table = static_cast<Ppa*>(mmap_large(base_bytes));

        // Initialize to some invalid PPA (e.g., max value)
        for (std::uint64_t i = 0; i < base_entries; ++i) {
            base_table[i] = static_cast<Ppa>(~0ULL);
        }

        // ---- FAST FTL MAPPING TABLE (fine, hybrid) ----
        if (cfg.fast_ftl_bytes > 0) {
            fast_entries_requested = units_for_granularity(
                cfg.fast_mapping,
                geom,
                cfg.subpages_per_page
            );

            std::uint64_t max_entries_by_space = cfg.fast_ftl_bytes / entry_size;
            fast_entries_allocated = std::min(fast_entries_requested, max_entries_by_space);
            fast_bytes = fast_entries_allocated * entry_size;

            if (fast_entries_allocated == 0) {
                fast_table = nullptr;
                fast_coverage_fraction = 0.0;
            } else {
                fast_table = new Ppa[fast_entries_allocated];
                for (std::uint64_t i = 0; i < fast_entries_allocated; ++i) {
                    fast_table[i] = static_cast<Ppa>(~0ULL);
                }
                fast_coverage_fraction =
                    static_cast<double>(fast_entries_allocated) /
                    static_cast<double>(fast_entries_requested);
            }
        }
    }

    ~FtlLayout() {
        if (base_table) {
            munmap(base_table, base_bytes);
        }
        delete[] fast_table;
    }

    // Utility: print a summary of what got allocated
    void print_summary(std::ostream& os = std::cout) const {
        os << "=== SSD Geometry ===\n";
        os << "User capacity: " << geom.user_capacity_gib() << " GiB\n";
        os << "Pages total:  " << geom.pages_total << "\n";
        os << "Blocks total: " << geom.blocks_total << "\n";
        os << "Page size:    " << geom.user_bytes_per_page
           << " bytes + " << geom.ecc_bytes_per_page << " ECC bytes\n\n";

        os << "=== Base Mapping ===\n";
        os << "Granularity:  " << mapping_to_string(cfg.base_mapping) << "\n";
        os << "Entries:      " << base_entries << "\n";
        os << "Table size:   " << base_bytes / (1024.0 * 1024.0) << " MiB\n\n";

        os << "=== Fast FTL (Hybrid) ===\n";
        os << "DRAM budget for fast FTL: " << cfg.fast_ftl_bytes / (1024.0 * 1024.0)
           << " MiB\n";
        os << "Granularity:  " << mapping_to_string(cfg.fast_mapping) << "\n";
        os << "Entries req.: " << fast_entries_requested << "\n";
        os << "Entries alloc: " << fast_entries_allocated << "\n";
        os << "Table size:   " << fast_bytes / (1024.0 * 1024.0) << " MiB\n";
        os << "Coverage:     " << (fast_coverage_fraction * 100.0) << "% of fast space\n";
    }

    static const char* mapping_to_string(MappingGranularity g) {
        switch (g) {
            case MappingGranularity::Block:   return "Block";
            case MappingGranularity::Page:    return "Page";
            case MappingGranularity::SubPage: return "SubPage";
            default:                          return "Unknown";
        }
    }
};

