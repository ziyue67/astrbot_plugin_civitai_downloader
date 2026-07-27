# AstrBot Civitai 下载器

发送 `image.civitai.com` 或 `civitai.red` 的图片、视频直链，插件会下载后以媒体消息回传。

也可使用命令：

```text
/civitai下载 https://image.civitai.com/.../image.jpeg
```

支持 `jpg`、`jpeg`、`png`、`webp`、`gif`、`avif`、`webm`、`mp4`、`mov`、`mkv`、`m4v`。单个文件最大 150 MB，下载超时为 90 秒。

## 安装

将本目录放入 AstrBot 的 `data/plugins/` 目录，或在插件管理页面从本地安装。重载插件后即可使用。
