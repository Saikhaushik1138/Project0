# Local NuttX apps change

`nuttx-apps.patch` preserves the only uncommitted tracked change found inside
the repository's submodules during upload preparation: deletion of the sample
`examples/webserver/httpd-fs/404.html` page. The patch was captured from the
submodule's working tree relative to its HEAD. Its base revision and SHA256
checksum are recorded in `manifest.json`.

The root repository retains the original upstream submodule reference. No
submodule commit was created or pushed, and the existing local change was not
modified. The patch is not needed for the PX4 SITL swarm workflow.

After a recursive clone, optionally reproduce the historical change from the
repository root:

```bash
git submodule update --init --recursive
git -C platforms/nuttx/NuttX/apps apply --check ../../../../archive/reorganization/submodule-changes/nuttx-apps.patch
git -C platforms/nuttx/NuttX/apps apply ../../../../archive/reorganization/submodule-changes/nuttx-apps.patch
```

Do not apply it again in the original workspace, where that deletion is already
present. If the check fails on another revision, inspect the difference before
applying the patch.
