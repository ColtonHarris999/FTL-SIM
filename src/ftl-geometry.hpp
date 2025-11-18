// ftl_geometry.hpp
#pragma once
#include "ftl-config.hpp"

struct SsdGeometry {
    // Derived from SsdConfig
    std::uint64_t bits_per_cell;
    std::uint64_t cells_per_page;
    std::uint64_t user_bytes_per_page;   // data bytes per page (ignoring ECC rounding issues)
    std::uint64_t ecc_bytes_per_page;    // ECC overhead per page (approx.)

    std::uint64_t pages_per_block;
    std::uint64_t blocks_total;
    std::uint64_t pages_total;

    std::uint64_t raw_capacity_bytes;    // bits_per_cell * cells * packages ...
    std::uint64_t user_capacity_bytes;   // user data capacity (excl. ECC)

    // convenience
    double user_capacity_gib() const {
        return static_cast<double>(user_capacity_bytes) / (1024.0 * 1024.0 * 1024.0);
    }
};

// Helper: compute how many bytes of ECC per page given ecc_bits_per_1k
inline std::uint64_t compute_ecc_bytes_per_page(
    const SsdConfig& cfg,
    std::uint64_t user_bytes_per_page
) {
    if (cfg.ecc_type == EccType::None || cfg.ecc_bits_per_1k == 0) {
        return 0;
    }

    // Approximate: ecc_bits_per_1k bits per 1024 bytes of user data.
    std::uint64_t units_1k = (user_bytes_per_page + 1023) / 1024;
    std::uint64_t ecc_bits = static_cast<std::uint64_t>(cfg.ecc_bits_per_1k) * units_1k;
    std::uint64_t ecc_bytes = (ecc_bits + 7) / 8;
    return ecc_bytes;
}

inline SsdGeometry derive_geometry(const SsdConfig& cfg) {
    if (cfg.bits_per_cell == 0 ||
        cfg.cells_per_page == 0 ||
        cfg.pages_per_block == 0 ||
        cfg.blocks_per_plane == 0 ||
        cfg.planes_per_die == 0 ||
        cfg.dies_per_package == 0 ||
        cfg.packages == 0) {
        throw std::invalid_argument("derive_geometry: invalid physical parameters");
    }

    SsdGeometry g{};

    g.bits_per_cell   = cfg.bits_per_cell;
    g.cells_per_page  = cfg.cells_per_page;
    g.pages_per_block = cfg.pages_per_block;

    // User bytes per page (ignoring spare / OOB area)
    std::uint64_t bits_per_page = g.bits_per_cell * g.cells_per_page;
    g.user_bytes_per_page = bits_per_page / 8;

    // ECC bytes per page (approximate)
    g.ecc_bytes_per_page = compute_ecc_bytes_per_page(cfg, g.user_bytes_per_page);

    // Total blocks/pages
    g.blocks_total =
        static_cast<std::uint64_t>(cfg.blocks_per_plane) *
        cfg.planes_per_die *
        cfg.dies_per_package *
        cfg.packages;

    g.pages_total = g.blocks_total * g.pages_per_block;

    g.user_capacity_bytes = g.pages_total * g.user_bytes_per_page;
    g.raw_capacity_bytes  = g.pages_total * (g.user_bytes_per_page + g.ecc_bytes_per_page);

    return g;
}
