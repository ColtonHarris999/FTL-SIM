## Hybrid log-block mapping FTL
### overview
- every logical block (same size as physical block) is mapped to a physical block & one or more log block(s)

### allocating
- writes always go to the next free page in the log block
- if a request sequentially writes to multiple LBAs within the same page, they are merged into one program operation
- otherwise, read-modify-write is performed for partial page writes (what about simply writing partial page and keeping track of valid data within the page?)

### Merging / Garbage Collection
- when the log block is full, a merge operation is triggered to consolidate data from the log block and the physical block into a new physical block. during this operation, the logical block is locked. another option is to allow multiple log blocks per logical block, allowing writes to continue while a merge is in progress.

### Questions
- how to exploit plane parallelism? should log block be chunked