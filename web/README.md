# LiDAR2CAD 项目主页

参考 StructRecon/转投/AAAI/web/index.html 的深色渐变首屏、吸顶导航、分节卡片、图件和结果表布局，为当前 LiDAR2CAD 英文稿制作的静态项目主页。

展示版采用独立标题首屏、位于 01 节之前的滑动对比窗口、编号章节和统一的图表与下载卡片样式。对比窗口默认宽度为内容区的 80%，相对上一版缩小 20% 并居中；右上角支持全屏查看。基础样式保留在 styles.css，展示层与响应式调整集中在 presentation.css。

## 预览

可直接用浏览器打开同目录的 index.html。页面不依赖 CDN、网络字体、前端框架或构建服务。推荐在项目根目录通过本地 HTTP 预览：

    python -m http.server 8000 --directory TII/web --bind 127.0.0.1

然后访问 http://127.0.0.1:8000/。

## 内容与交互

- 项目介绍、方法架构、双向校正与证据条件化补全。
- 标题下方的全场景窗口固定右侧为 Complete reconstruction；第一行选择 LiDAR 点云投影、LiDAR-only 或设计 CAD，第二行选择 P. Hough、DP-Contour、RANSAC、Morph-Skel、LSD、FLD 或 EDLines。
- 可直接拖动图片或下方滑杆；滑杆支持键盘方向键、Home 和 End。手机端第二行基线块可横向滚动；所有图件保留同一视域、纵横比例、比例尺和像素尺寸。
- 窗口右上角的 Fullscreen 按钮进入全屏；可用 Exit fullscreen 或 Esc 退出。全屏保持完整图件等比例显示并保留对比滑杆；不支持原生全屏的浏览器使用页面内全屏回退。
- 四个 ROI 的四阶段对比，支持切换区域、点击放大及 Esc 关闭。
- 主实验、受控比较、消融、额外设施和敏感性分析。
- 来源可追溯的结构层与设施语义图层说明。
- 评估范围、效率统计边界和证据可用性说明。
- 本地论文 PDF、源码和数据压缩包下载；未编造作者、录用状态或远程仓库地址。

页面中的数值来自当前稿件及 TII/results/author_results_20261025/author_results.json。导入结果为作者确认的异机实验汇总，本次制网页未重跑实验。配对试验、完整流程、全场景输出和四区域评估的统计范围在页面中分别说明。

## 更新图件和论文

build_assets.py 将论文中的原始 PDF 图件转换为适合网页的 WebP，并原样复制当前论文 PDF；不会修改论文目录。

    python TII/web/build_assets.py

依赖 Python 的 pymupdf、pillow。共导出 22 张图，来源、尺寸和 SHA-256 记录在 assets/manifest.json。修改论文正文和表格后，需同步核对 index.html 中的介绍与数值；导出脚本只更新二进制素材，不自动改写网页文本。

全场景滑动对比另由以下脚本生成：

    python TII/web/build_comparisons.py

该脚本从论文冻结的点云质心、完整场景几何、作者圈注设计稿和七种方法线划导出 11 张 1800 × 1480 WebP。全部采用同一地图视域和比例尺，不修改原始几何、不重新运行实验。设计图使用归档初始全局配准上的作者红圈标注；完整输出包含墙柱、保留设计与设施层，不意味着每条保留设计均已现场验证。依赖 numpy、matplotlib、pillow、pymupdf、shapely、ezdxf；保留图件依赖的原始设计 DXF。来源哈希、路径计数和显示策略记录在 assets/comparison-manifest.json，脚本检查保护源文件未变化。

## 检查

    python TII/web/check_homepage.py

依赖 playwright，默认优先使用已安装的 Windows Edge，也可通过 --browser 指定 Chromium 可执行文件。检查资源、锚点、320–1440 px 宽度、全部十组对比切换、拖动和键盘操作、图件尺寸与哈希、区域切换、图件放大、折叠面板、PDF 与发布包下载，以及无 JavaScript 的本地打开；截图与报告保存于 .checks/。

## 源码与数据发布包

源码整理在 TII/opensource/，原始代码和数据目录不修改。源码采用 MIT，选定的原创汇总数据和合成样例采用 CC BY 4.0；不对原始场景数据或第三方软件擅自改许可。包含 15 张原始汇总表的无损 CSV、来源 JSON 和可执行合成示例。不含原始扫描、工程图、模型权重或未经核对的历史真值；不是完整场景基准发布。

    python TII/web/build_release.py
    python TII/opensource/scripts/verify_release.py
    python TII/opensource/scripts/run_joint_demo.py

构建压缩包及校验文件到 assets/releases/，主页提供真实相对路径下载。源代码快照不保证与异机实验版本一致。准备远程仓库和数据授权事项见 TII/opensource/docs/PUBLISHING.md。当前未上传公网。

## 静态托管

将 index.html、styles.css、presentation.css、script.js 和整个 assets/ 文件夹一起上传至任意静态托管服务即可。无需上传 Python 脚本、README 或 .checks/。当前只创建本地页面，未进行网络发布。

发布前请确认论文适合公开；如需保持匿名，不要添加身份相关内容。获得正式代码仓库、数据或视频链接后，再更新资源区。浏览器标签、摘要及主题色元信息已配置；未设置未知的正式域名、作者信息或社交分享 URL。
