# torrent_analyze_HoshinoBot

适用于HoshinoBot的磁链分析插件，通过whatslink.info API。

## 安装方法
1. 在hoshino/modules下clone本仓库`git clone https://github.com/SlightDust/torrent_analyze_HoshinoBot.git`
2. 在hoshino/config/__bot__.py中加入

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

## 遗留问题
1. whatslink.info有频率限制。触发频率限制时，会反复调用20次接口，每次间隔3秒。
2. API能返回截图链接，但是没想好有什么安全的发图方式，姑且注释掉了。

## 日志
2023/12/27 好的开始
