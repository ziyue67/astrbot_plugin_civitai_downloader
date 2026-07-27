# AstrBot Civitai 下载器

发送 `image.civitai.com` 或 `civitai.red` 的图片、视频直链，插件会下载后以媒体消息回传。

也可使用命令：

```text
/civitai下载 https://image.civitai.com/.../image.jpeg
```

支持 `jpg`、`jpeg`、`png`、`webp`、`gif`、`avif`、`webm`、`mp4`、`mov`、`mkv`、`m4v`。单个文件最大 150 MB，下载超时为 90 秒。

## 安装

将本目录放入 AstrBot 的 `data/plugins/` 目录，或在插件管理页面从 GitHub 仓库安装。重载插件后即可使用。

视频直链即使 URL 扩展名是 `.webm`，Civitai 也可能实际返回 MP4；插件会按响应的媒体类型保存并回传。
