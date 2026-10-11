# systemd user units (EC2 host)

Install path on the host:

```text
~/.config/systemd/user/multibot2-bot.service
```

Enable / reload (as the `ubuntu` user):

```bash
systemctl --user daemon-reload
systemctl --user enable --now multibot2-bot.service
```

## Disk / temp dirs

`/tmp` on this host is a small tmpfs. The unit therefore sets both:

- `TEMP_DIR=%h/data/multibot2/tmp` — honored by `check_disk_space` and `TempManager`
- `TMPDIR=%h/data/multibot2/tmp` — honored by Python `tempfile` / stdlib

`ExecStartPre` creates the directory. Keep `TEMP_DIR` in `.env` aligned with the same path.
