# torrent_analyze_HoshinoBot

适用于HoshinoBot的磁链分析插件，通过whatslink.info API。

## 安装方法
1. 在hoshino/modules下clone本仓库`git clone https://github.com/SlightDust/torrent_analyze_HoshinoBot.git`
2. 在hoshino/config/\_\_bot\_\_.py中加入

```python
MODULES_ON = {
...
'torrent_analyze_HoshinoBot',  # 验车
}
```
3. 重启hoshino

功能默认开启。服务叫`torrent_analyze`。

## 使用说明
|指令|说明|指令示例|
|----|----|----|
| 验车 种子ID或磁链 | 去whatslink.info查种子信息 | 验车 magnet:?xt=urn:btih:32181995C9D274FCFBE0A5E427F047210E82A53D |
| set验车[高斯/图片][开/关][0~10] | 修改本群验车参数 | **set验车高斯开10** 开启图片模式的高斯模糊 10是级别<br>**set验车图片开** 开启图片返回 |

查询结果会缓存到插件目录，方便之后查相同种子时候快速响应。

## 遗留问题
1. whatslink.info有频率限制。触发频率限制时，会反复调用20次接口，每次间隔3秒。

## 日志
2024/9/27 好的开始

2024/10/16 新增图片功能