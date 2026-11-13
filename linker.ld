ENTRY(_start)
MEMORY {
    rom (rx) : ORIGIN = 0x08000000, LENGTH = 32M
    iwram (rwx) : ORIGIN = 0x03000000, LENGTH = 28K
    ewram (rwx) : ORIGIN = 0x02000000, LENGTH = 256K
}
SECTIONS {
    .text : { KEEP(*(.crt0)) *(.text .text.*) . = ALIGN(4); } > rom
    .rodata : { *(.rodata .rodata.*) . = ALIGN(4); } > rom
    .ARM.exidx : { *(.ARM.exidx*) } > rom
    .iwram : {
        __iwram_start = .;
        *(.iwram .iwram.*) *(.data .data.*)
        . = ALIGN(4); __iwram_end = .;
    } > iwram AT>rom
    __iwram_lma = LOADADDR(.iwram);
    .bss (NOLOAD) : {
        __bss_start = .; *(.bss .bss.* COMMON)
        . = ALIGN(4); __bss_end = .;
    } > iwram
    .ewram_bss (NOLOAD) : {
        __ewram_bss_start = .; *(.ewram_bss .ewram_bss.*)
        . = ALIGN(4); __ewram_bss_end = .;
    } > ewram
    /DISCARD/ : { *(.comment) *(.ARM.attributes) *(.note*) }
}
