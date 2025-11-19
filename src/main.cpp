#include <sim/setup/setup.hpp>
#include <sim/ftl/ftl.hpp>
#include <iostream>

int main(int argc, char** argv) {
    using namespace sim::setup;
    using namespace sim::ftl;

    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <config.yaml>\n";
        return 1;
    }

    SetupConfig cfg = load_ssd_config(argv[1]);
    FtlLayout layout(cfg);
    layout.print_summary();
}
