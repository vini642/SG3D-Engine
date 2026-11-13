/* Generated from OBJ by tools/obj_to_sg3d.py. Edit the OBJ instead. */
#ifndef SG3D_PYRAMID_H
#define SG3D_PYRAMID_H
#include "sg3d.h"
static const SG3DVertex pyramid_vertices[] = {
    {-256, -256, -256},
    {256, -256, -256},
    {0, 256, 0},
    {256, -256, 256},
    {-256, -256, 256},
};
static const SG3DFace pyramid_faces[] = {
    {0, 1, 2, 0, 0, {SG3D_UV(0,512), SG3D_UV(512,512), SG3D_UV(256,0)}},
    {1, 3, 2, 0, 0, {SG3D_UV(0,512), SG3D_UV(512,512), SG3D_UV(256,0)}},
    {3, 4, 2, 0, 0, {SG3D_UV(0,512), SG3D_UV(512,512), SG3D_UV(256,0)}},
    {4, 0, 2, 0, 0, {SG3D_UV(0,512), SG3D_UV(512,512), SG3D_UV(256,0)}},
    {4, 3, 1, 0, 0, {SG3D_UV(0,0), SG3D_UV(512,0), SG3D_UV(512,512)}},
    {4, 1, 0, 0, 0, {SG3D_UV(0,0), SG3D_UV(512,512), SG3D_UV(0,512)}},
};
static const SG3DMesh pyramid_mesh = {
    pyramid_vertices, 5, pyramid_faces, 6
};
#endif
