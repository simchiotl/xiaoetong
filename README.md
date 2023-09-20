# Download Xiaoet

> 小鹅通资源下载工具

## 一、安装

#### 1. 安装python 依赖

```
pip install -r requirements.txt
```

#### 2. 安装ffmpeg

```
CentOS
https://download1.rpmfusion.org/free/el/updates/7/x86_64/repoview/letter_f.group.html

Ubuntu
https://launchpad.net/ubuntu/+source/ffmpeg
```

## 二、使用方法示例

在同目录下新建`config.json`，需包含：

```json
{
  "appid": "appxxxxx",
  "user_id": "u_xxxx_xxxx",
  "cookie": "xxxx"
}
```

下载视频
```shell
python main.py download <ResourceID1> <ResourceID2> ...
```

列出课程下所有视频：
```shell
python main.py list <courseID>
```

备注：

1. 登录需要微信扫码登录，session时效性为4小时，更换店铺需要重新设置`config.json`
2. 默认下载目录为同级download目录下，下载完成后视频为分段，将自动合成。
3. 店铺为`appxxxx`,专栏ID(ProductID)为`p_xxxx_xxx`,资源ID分为视频与音频分别为`v_xxx_xxx`、`a_xxx_xxx`，课程ID为`term_xxxx_xxxx`.