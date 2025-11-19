// sim/ftl/ftl-layout.hpp
#pragma once


#include <cstddef>
#include <cstdint>
#include <iosfwd>
#include <iostream>

#include <sim/setup/enums.hpp>
#include <sim/setup/setup-config.hpp>
#include <sim/ftl/ftl-config.hpp>
#include <sim/ftl/ftl-geometry.hpp>

namespace sim::ftl {

// How many logical units exist for a given mapping granularity?
std::uint64_t units_for_granularity(
    sim::setup::MappingGranularity gran,
    const SsdGeometry& geom,
    std::uint32_t subpages_per_page
);

class FtlLayout {
public:
    explicit FtlLayout(const sim::setup::SetupConfig& cfg);
    ~FtlLayout();

    void print_summary(std::ostream& os = std::cout) const;

private:
    static const char* mapping_to_string(sim::setup::MappingGranularity g);

    sim::setup::SetupConfig cfg;
    SsdGeometry  geom;

    // Base (slow) mapping table
    std::uint64_t base_entries;
    std::size_t   base_bytes;
    Ppa*          base_table;

    // Fast (DRAM) mapping table
    std::uint64_t fast_entries_requested;
    std::uint64_t fast_entries_allocated;
    std::size_t   fast_bytes;
    Ppa*          fast_table;

    double        fast_coverage_fraction;
};

} // namespace sim::ftl
