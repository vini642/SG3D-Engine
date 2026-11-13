# Before a public release

- [ ] **Resolve upstream renderer/code redistribution rights** and preserve all required copyright notices.
- [ ] Decide/confirm a license *only* for material you have authority to license; then add `LICENSE`.
- [ ] Review example assets for rights. Avoid bundling copyrighted Pokémon/Nintendo graphics, sounds, ROMs or ISOs.
- [ ] Test a clean clone: install Pillow, launch GUI, open sample, export valid ROM.
- [ ] Verify third-person orbit, car controller, sky panorama, and native-resolution HUD on mGBA.
- [ ] Verify input, sound, performance and saving/opening projects on hardware where possible.
- [ ] Check standard vs embedded projects, custom export filename, and missing asset warnings.
- [ ] Verify source contains no local paths, secrets, paid tools, proprietary assets, or generated build outputs.
- [ ] Decide whether to attach sample `.gba` builds to a GitHub Release **after licensing is cleared**.
- [ ] Create a signed-off version tag and publish release notes.

Until the copyright/permission requirement is resolved, keep the GitHub repository **private**.
