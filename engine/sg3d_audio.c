/* SG3D v0.11.1: hardware-timed Direct Sound A (8,192 Hz, mono PCM).
 * The old code stopped after a number of *rendered frames*, which was wrong
 * whenever 3D rendering ran below 60 FPS. DMA then read beyond the PCM.
 * Timer 0 is the audio clock; cascaded Timer 1 counts exactly how many
 * PCM samples have played. Its single end-of-sound IRQ shuts down DMA.
 */
#include "sg3d_audio.h"

#ifdef SG3D_AUDIO_HOST_TEST
extern volatile uint16_t *sg3d_test_io16(uint32_t address);
extern volatile uint32_t *sg3d_test_io32(uint32_t address);
#define IO16(addr) (*sg3d_test_io16(addr))
#define IO32(addr) (*sg3d_test_io32(addr))
#else
#define IO16(addr) (*(volatile uint16_t *)(addr))
#define IO32(addr) (*(volatile uint32_t *)(addr))
#endif

#define REG_SOUNDCNT_H IO16(0x04000082)
#define REG_SOUNDCNT_X IO16(0x04000084)
#define REG_DMA1SAD    IO32(0x040000BC)
#define REG_DMA1DAD    IO32(0x040000C0)
#define REG_DMA1CNT_H IO16(0x040000C6)
#define REG_TM0CNT_L   IO16(0x04000100)
#define REG_TM0CNT_H   IO16(0x04000102)
#define REG_TM1CNT_L   IO16(0x04000104)
#define REG_TM1CNT_H   IO16(0x04000106)
#define REG_IE         IO16(0x04000200)
#define REG_IF         IO16(0x04000202)
#define REG_IME        IO16(0x04000208)
#define REG_IRQ_VECTOR IO32(0x03007FFC)
#define IRQ_TIMER1      0x0010u
#define TIMER0_8192HZ   0xF800u /* 2^24 / 8192 = 2048 CPU cycles */

/* Also used from the IRQ, so never change IME inside this helper. */
static void audio_stop_hardware(void){
    REG_TM0CNT_H=0;
    REG_TM1CNT_H=0;
    REG_DMA1CNT_H=0;
    REG_SOUNDCNT_H=0x0B04; /* reset FIFO A to silence, full volume, both speakers */
}

/* BIOS calls the pointer at 0x03007FFC for IRQ dispatch. This first
 * version of SG3D owns that handler (it only enables Timer 1 IRQs).
 * Keep the handler in fast internal WRAM for stable audio cut-off.
 */
void sg3d_audio_irq(void) __attribute__((section(".iwram")));
void sg3d_audio_irq(void){
    uint16_t pending=REG_IF;
    if(pending & IRQ_TIMER1){
        audio_stop_hardware();
    }
    REG_IF=pending; /* W1C: acknowledge any pending IRQ flags */
}

void sg3d_audio_init(void){
    REG_IME=0;
    audio_stop_hardware();
    REG_SOUNDCNT_X=0x0080;
    REG_IRQ_VECTOR=(uint32_t)(uintptr_t)&sg3d_audio_irq;
    REG_IF=IRQ_TIMER1;  /* discard a stale audio completion interrupt */
    REG_IE=IRQ_TIMER1;  /* engine currently has no other IRQ clients */
    REG_IME=1;
}

void sg3d_audio_stop(void){
    uint16_t ime=REG_IME;
    REG_IME=0;
    audio_stop_hardware();
    REG_IF=IRQ_TIMER1;
    REG_IME=ime;
}

void sg3d_audio_play(const int8_t *samples,uint32_t length){
    /* Converter limits individual effects to 16,384 samples (2 seconds).
       Reject anything that would overflow Timer 1's 16-bit counter. */
    if(!samples || !length || length>65535u){sg3d_audio_stop();return;}
    uint16_t ime=REG_IME;
    REG_IME=0;
    audio_stop_hardware();
    REG_IF=IRQ_TIMER1;
    REG_TM0CNT_L=TIMER0_8192HZ;
    REG_TM1CNT_L=(uint16_t)(0u-length); /* overflows after length samples */
    REG_DMA1SAD=(uint32_t)(uintptr_t)samples;
    REG_DMA1DAD=0x040000A0;
    REG_DMA1CNT_H=0xB600; /* FIFO DMA, 32-bit, repeating */
    REG_TM1CNT_H=0x00C4; /* enable + cascade Timer 0 + IRQ at end */
    REG_TM0CNT_H=0x0080; /* last: start playing audio at 8192 Hz */
    REG_IME=ime;
}

/* Kept for backward compatibility with v0.11 generated C scenes.
   Playback length no longer depends on frames or game framerate. */
void sg3d_audio_tick(void){}
