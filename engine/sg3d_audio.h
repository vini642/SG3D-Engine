#ifndef SG3D_AUDIO_H
#define SG3D_AUDIO_H
#include <stdint.h>
/* One-voice 8192 Hz signed PCM on Direct Sound A. New effects replace old.
 * Audio playback ends via hardware Timer 1 interrupt regardless of FPS.
 * Timer 0, Timer 1, DMA1, and the IRQ vector are currently reserved for audio. */
void sg3d_audio_init(void);
void sg3d_audio_play(const int8_t *samples,uint32_t length);
void sg3d_audio_stop(void);
void sg3d_audio_tick(void); /* legacy no-op, safe to call from old scenes */
#endif
