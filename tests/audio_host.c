/* Host-side register tests for hardware sample-accurate sound shutdown. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#define IREG(addr) regs16[((addr)-0x04000000)/2]
static volatile uint16_t regs16[0x300/2];
static volatile uint32_t regs32[0x300/4];
static volatile uint32_t bios_irq_ptr;
volatile uint16_t *sg3d_test_io16(uint32_t address) {
    if (address<0x04000000 || address>=0x04000300 || (address&1)) abort();
    return &IREG(address);
}
volatile uint32_t *sg3d_test_io32(uint32_t address) {
    if (address==0x03007FFC) return &bios_irq_ptr;
    if (address<0x04000000 || address>=0x04000300 || (address&3)) abort();
    return &regs32[(address-0x04000000)/4];
}
void sg3d_audio_init(void);
void sg3d_audio_play(const int8_t *,uint32_t);
void sg3d_audio_stop(void);
void sg3d_audio_tick(void);
void sg3d_audio_irq(void);
static void check(int result,const char *why){if(!result){fprintf(stderr,"FAIL: %s\n",why);exit(1);}}
int main(void){
    static int8_t pcm[16384];
    sg3d_audio_init();
    check(IREG(0x04000200)==0x0010,"Timer1 IRQ enabled");
    check(IREG(0x04000208)==1,"interrupt master enabled");
    check(bios_irq_ptr!=0,"BIOS vector assigned");
    for (uint32_t length=1;length<=16384;length = length==1 ? 128 : length==128 ? 2048 : length==2048 ? 16384 : 65536){
        sg3d_audio_play(pcm,length);
        check(IREG(0x04000100)==0xF800,"Timer0 8192 Hz reload");
        check(IREG(0x04000104)==(uint16_t)(0u-length),"exact PCM sample count preload");
        check(IREG(0x04000106)==0xC4,"Timer1 enabled cascaded with IRQ");
        check(IREG(0x04000102)==0x80,"Timer0 enabled");
        check(IREG(0x040000C6)==0xB600,"DMA1 enabled for FIFO");
        /* Any number of rendered frames must have NO effect on sound length. */
        for (int i=0;i<250;i++)sg3d_audio_tick();
        check(IREG(0x04000102)==0x80,"frame-rate-independent playback");
        /* Simulate Timer1 overrun IRQ at exactly the selected sample count. */
        IREG(0x04000202)=0x10;
        sg3d_audio_irq();
        check(IREG(0x04000102)==0,"Timer0 stopped at sample end");
        check(IREG(0x04000106)==0,"Timer1 stopped at sample end");
        check(IREG(0x040000C6)==0,"DMA1 stopped at sample end");
    }
    sg3d_audio_play(pcm,512);
    sg3d_audio_play(pcm,256); /* new effect restarts sample counter */
    check(IREG(0x04000104)==(uint16_t)(0u-256),"replacement sound restarts length");
    sg3d_audio_stop();
    check(IREG(0x040000C6)==0,"manual stop halts DMA");
    sg3d_audio_play(pcm,65536); /* invalid exceeds timer's 16 bits */
    check(IREG(0x040000C6)==0,"oversized sound safely rejected");
    puts("PASS: IRQ, sample lengths 1/128/2048/16384, frame independence, restarts, manual stop, invalid length");
    return 0;
}
