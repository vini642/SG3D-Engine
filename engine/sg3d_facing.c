#include "sg3d_facing.h"

/* 0..64 ratio -> 0..32 angle (quarter of a right angle).
   Generated offline from round(atan(i/64) * 128 / pi). */
static const uint8_t atan_table[65] = {
    0, 1, 1, 2, 3, 3, 4, 4, 5, 6, 6, 7, 8,
    8, 9, 9, 10, 11, 11, 12, 12, 13, 13, 14, 15, 15,
    16, 16, 17, 17, 18, 18, 19, 19, 20, 20, 21, 21, 22,
    22, 23, 23, 24, 24, 25, 25, 25, 26, 26, 27, 27, 27,
    28, 28, 29, 29, 29, 30, 30, 30, 31, 31, 31, 32, 32,
};

static uint32_t magnitude(int32_t n) {
    /* Works for INT32_MIN without signed overflow. */
    return n < 0 ? (~(uint32_t)n + 1u) : (uint32_t)n;
}

/* Six-step binary fractional ratio, avoiding compiler division helpers.
   Output 0..64 for numerator/denominator, numerator <= denominator. */
static unsigned fraction_64(uint32_t numerator, uint32_t denominator) {
    unsigned value = 0;
    if (numerator >= denominator) return 64;
    while (denominator > (1u << 29)) {
        numerator >>= 1;
        denominator >>= 1;
    }
    for (unsigned i=0;i<6;i++) {
        numerator <<= 1;
        value <<= 1;
        if (numerator >= denominator) {
            numerator -= denominator;
            value |= 1u;
        }
    }
    return value;
}

static uint8_t heading(int32_t dx, int32_t dz) {
    uint32_t ax = magnitude(dx), az = magnitude(dz);
    uint8_t quarter;
    if (az >= ax) quarter = atan_table[fraction_64(ax,az)];
    else quarter = (uint8_t)(64u - atan_table[fraction_64(az,ax)]);
    if (dz >= 0) return (uint8_t)(dx >= 0 ? quarter : (256u-quarter));
    return (uint8_t)(dx >= 0 ? (128u-quarter) : (128u+quarter));
}

void sg3d_facing_capture(SG3DFacing *state, const SG3DTransform *transform) {
    state->previous_x = transform->x;
    state->previous_z = transform->z;
}

void sg3d_facing_update(SG3DFacing *state, SG3DTransform *transform) {
    if (!state->enabled) return;
    int32_t dx=(int32_t)((uint32_t)transform->x-(uint32_t)state->previous_x);
    int32_t dz=(int32_t)((uint32_t)transform->z-(uint32_t)state->previous_z);
    /* Ignore subpixel jitter, but finish turning toward the last heading
       after movement stops. Don't turn until a direction is established. */
    if (magnitude(dx) >= 2u || magnitude(dz) >= 2u) {
        state->target=(uint8_t)(heading(dx,dz)+state->offset);
        state->has_target=1u;
    }
    if (!state->has_target) return;
    uint8_t goal=state->target;
    if (state->smoothing == 255u) {
        transform->yaw = goal;
        return;
    }
    int delta=(int8_t)(uint8_t)(goal-transform->yaw); /* shortest arc */
    if (!delta) return;
    unsigned amount=(unsigned)(delta<0?-delta:delta);
    unsigned step=(amount*state->smoothing + 127u) >> 8;
    if (step==0u) step=1u;
    if (step>amount) step=amount;
    transform->yaw=(uint8_t)(transform->yaw+(delta<0?-(int)step:(int)step));
}
