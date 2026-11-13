#ifndef SG3D_CONTROLS_H
#define SG3D_CONTROLS_H
#include "sg3d.h"
#include "sg3d_physics.h"
#include <stdint.h>
typedef struct { int32_t speed; } SG3DVehicle;
/* Angles 0..255; offsets/speeds in 8.8. */
/* Split update: apply input BEFORE scripted camera-relative movement, then
   place the camera AFTER physics has moved its target. */
void sg3d_orbit_input(uint16_t keys, uint8_t *yaw, int8_t *pitch, uint8_t turn_speed);
void sg3d_orbit_place(SG3DCamera *camera, const SG3DTransform *target,
                      uint8_t yaw, int8_t pitch, int32_t radius, int32_t height);
/* Backward-compatible convenience wrapper for older generated games. */
void sg3d_orbit_camera(SG3DCamera *camera, const SG3DTransform *target,
                       uint16_t keys, uint8_t *yaw, int8_t *pitch,
                       int32_t radius, int32_t height, uint8_t turn_speed);
void sg3d_move_relative(SG3DPhysicsBody *bodies,unsigned count,unsigned object,
                        uint8_t camera_yaw,int32_t strafe,int32_t forward);
void sg3d_drive_vehicle(SG3DPhysicsBody *bodies,unsigned count,unsigned object,
                        SG3DVehicle *state,uint16_t keys,int32_t accel,
                        int32_t maxspeed,int32_t drag,uint8_t turn);
#endif
