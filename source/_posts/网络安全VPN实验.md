---
title: 网络安全VPN实验
date: 2024-09-10 03:26:38
updated: 2025-03-03
tags:
  - 网络安全
---

## 使用IP命令搭建基于隧道的虚拟专有网络

### 登录和修改主机名称

双击桌面Xshell5图标，在弹出的界面登陆主机 `192.168.1.11`和 `192.168.2.11`这两台主机.密码为 `Simplexue123`：

![1713354486382](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713354486382.png)

分别修改主机名：

```vim
# hostnamectl set-hostname vpn1
# hostnamectl set-hostname vpn2
```

![1713354588318](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713354588318.png)

![1713354601309](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713354601309.png)

重新登陆两台主机后：

![1713354665681](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713354665681.png)

![1713354681735](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713354681735.png)

### vpn1和vpn2主机分别加载gre内核模块并检查

加载ip_gre内核模块

```autoit
[root@vpn1 ~]# modprobe ip_gre
```

查询ip_gre模块是否加载：

```autoit
[root@vpn1 ~]# lsmod | grep gre
```

![1713354787872](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713354787872.png)

![1713354834525](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713354834525.png)

### 配置tunnel（GRE隧道）使它们互通

vpn1创建一个GRE类型隧道设备gre1, 并设置对端IP为192.168.2.11。隧道数据包将被从192.168.1.11也就是本地IP地址发起，其TTL字段被设置为255。隧道设备分配的IP地址为10.10.10.1，掩码为255.255.255.0。

#### 创建GRE类型隧道设备gre1，并验证是否添加成功

```perl
[root@vpn1 ~] ip tunnel add gre1 mode gre remote 192.168.2.11 local 192.168.1.11 ttl 255
[root@vpn1 ~] ip a | grep gre1
```

![1713356095709](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713356095709.png)

#### 启动gre1并分配ip地址10.10.10.1，检测是否添加并启动

```shell
# ip link set gre1 up
# ip addr add 10.10.10.1/24 dev gre1
# ip a | grep gre1
```

![1713356284531](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713356284531.png)

#### 查看隧道状态

```bash
ip -d link show
```

![1713356389861](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713356389861.png)

#### 对vpn2复刻上面的操作

vpn2创建一个GRE类型隧道设备gre1, 并设置对端IP为192.168.1.11。隧道数据包将被从192.168.2.11也就是本地IP地址发起，其TTL字段被设置为255。隧道设备分配的IP地址为10.10.10.2，掩码为255.255.255.0。

```shell
# ip tunnel add gre1 mode gre remote 192.168.1.11 local 192.168.2.11 ttl 255
# ip link set gre1 up
# ip addr add 10.10.10.2/24 dev gre1
# ip a | grep gre1
```

![1713356613248](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713356613248.png)

#### 测试隧道是否通

```autoit
[root@vpn1 ~]# ping 10.10.10.2
```

![1713356736749](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713356736749.png)

### 卸载GRE模块

```1c
# rmmod ip_gre
# lsmod | grep gre
```

![1713357022456](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713357022456.png)

![1713357038046](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713357038046.png)

## 使用加密工具OpenSSL创建加密密钥

### 查看openssl命令的基本帮助

```verilog
[root@vpn1 ~]# openssl genrsa -
//密钥位数，建议1024及以上
usage: genrsa [args] [numbits]
//生成的密钥使用des方式进行加密
 -des            encrypt the generated key with DES in cbc mode
//生成的密钥使用des3方式进行加密
 -des3           encrypt the generated key with DES in ede cbc mode (168 bit key)
 -idea           encrypt the generated key with IDEA in cbc mode
//生成的密钥还是要seed方式进行
 -seed           encrypt PEM output with cbc seed
//生成的密钥使用aes方式进行加密
 -aes128, -aes192, -aes256 encrypt PEM output with cbc aes
//生成的密钥使用camellia方式进行加密
 -camellia128, -camellia192, -camellia256
                 encrypt PEM output with cbc camellia
//生成的密钥文件，可从中提取公钥
 -out file       output the key to 'file
//指定密钥文件的加密口令，可从文件、环境变量、终端等输入
 -passout arg    output file pass phrase source
//选择指数e的值，默认指定该项，e值为65537
 -f4             use F4 (0x10001) for the E value
//选择指数e的值，默认值为65537，使用该选项则指数指定为3
 -3              use 3 for the E value
//指定三方加密库或者硬件
 -engine e       use engine e, possibly a hardware device.
//产生随机数的种子文件
 -rand file:file:...
                 load the file (or the files in the directory) into
                 the random number generator
```

![1713357173703](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713357173703.png)

### 生成私钥

#### 生产RSA私钥(无加密)

```autoit
[root@vpn1 ~]# openssl genrsa -out rsa_private.key 2048 
[root@vpn1 ~]# ll rsa_private.key 
```

![1713357718410](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713357718410.png)

#### 生成rsa_private.key私钥对应的公钥

```autoit
[root@vpn1 ~]# openssl rsa -in rsa_private.key -pubout -out rsa_public.key 
[root@vpn1 ~]# ll rsa_public.key 
```

![1713357995140](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713357995140.png)

### 生成RSA含密码（使用aes256加密）公私钥

```autoit
# 其中 passout 代替shell 进行密码输入，否则会提示输入密码
[root@vpn1 ~]# openssl genrsa -aes256 -passout pass:simple -out rsa__aes_private.key 2048
# 生成其对应的公钥，需要输入密码，其中 pass 代替shell 进行密码输入，否则会提示输入密码；
[root@vpn1 ~]# openssl rsa -in rsa__aes_private.key -passin pass:simple -pubout -out rsa_aes_public.key
[root@vpn1 ~]# ll rsa_aes_public.key
```

![1713358665590](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713358665590.png)

![1713358684364](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713358684364.png)

### 加密与非加密之间的转换

```sas
# 私钥转非加密
openssl rsa -in rsa__aes_private.key -passin pass:simple -out rsa_private.key 
# 私钥转加密 
openssl rsa -in rsa_private.key -aes256 -passout pass:simple -out rsa__aes_private.key
```

![1713358980816](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713358980816.png)

![1713358994180](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713358994180.png)

### 生成自签名证书

```ldif
# 生成 RSA 私钥和自签名证书req是证书请求的子命令，
-newkey rsa:2048 -keyout private_key.pem 表示生成私钥(PKCS8格式)；
-nodes 表示私钥不加密，若不带参数将提示输入密码；
-x509表示输出证书；
-days365 为有效期，此后根据提示输入证书拥有者信息；
```

```apache
openssl req -newkey rsa:2048 -nodes -keyout rsa_private.key -x509 -days 365 -out cert.crt
```

若执行自动输入，可使用-subj选项：

```apache
openssl req -newkey rsa:2048 -nodes -keyout rsa_private.key -x509 -days 365 -out cert.crt -subj "/C=CN/ST=BJ/L=BJ/O=simpleedu/OU=edu/CN=simple/emailAddress=simple@simpleedu.com"
```

![1713359440320](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713359440320.png)

使用 已有RSA 私钥生成自签名证书

`-new` 指生成证书请求，加上 `-x509` 表示直接输出证书，`-key` 指定私钥文件，其余选项与上述命令相同

```maxima
openssl req -new -x509 -days 365 -key rsa_private.key -out cert.crt
```

![1713359626377](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713359626377.png)

### 生成签名请求及CA 签名

```pgsql
# 使用 RSA私钥生成 CSR 签名请求 
openssl genrsa -aes256 -passout pass:simpleedu -out server.key 2048 openssl req -new -key server.key -out server.csr  
\* 此时生成的 csr签名请求文件可提交至 CA进行签发 *\
```

![1713360035471](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713360035471.png)

## OpenVPN的安装配置

### 在vpn1机器安装openvpn并验证

修改yum源

```coffeescript
[root@vpn1 ~]# vim /etc/yum.repos.d/simple.repo
# 将 baseurl=http://192.168.50.50/yum 修改为 baseurl=file:///data/repos
[root@vpn1 ~]# yum clean all
[root@vpn1 ~]# yum install openvpn -y
```

![1713361912967](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713361912967.png)

![1713361949114](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713361949114.png)

```autoit
[root@vpn1 ~]# rpm -qa | grep openvpn
```

![1713362017412](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713362017412.png)

### 修改openvpn的配置文件server.conf配置文件

拷贝模板文件到配置文件目录下

```swift
[root@vpn1 ~]# cp /usr/share/doc/openvpn-2.4.4/sample/sample-config-files/server.conf /etc/openvpn/ 
[root@vpn1 ~]# ls /etc/openvpn/server.conf 
```

![1713362660770](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713362660770.png)

修改openvpn服务端的配置文件

```autoit
[root@vpn1 ~]# vim /etc/openvpn/server.conf
# 指定TCP协议(使用TCP协议如果连接上VPN后网络很慢，可以更改成使用UDP协议)
```

![1713362967403](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713362967403.png)

配置DNS

设置启动用户

![1713363044137](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713363044137.png)

注释掉 explicit-exit-notify 1

![1713363104041](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713363104041.png)

安装密钥生成软件 `shell [root@vpn1 ~]# yum install easy-rsa -y `

![1713363138434](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713363138434.png)

准备配置证书文件

```swift
拷贝文件到/etc/openvpn
[root@vpn1 ~]# cp -r /usr/share/easy-rsa/ /etc/openvpn/ 
[root@vpn1 ~]# ls /etc/openvpn/easy-rsa/ 
```

![1713363200283](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713363200283.png)

配置生成证书的环境变量.并使之生效

```routeros
[root@vpn1 ~]# vim /etc/openvpn/easy-rsa/2.0/vars  
# 现只修改如下几条，可根据自己情况进行修改 
export KEY_COUNTRY="CN" 
export KEY_PROVINCE="BJ" 
export KEY_CITY="BEIJING" 
export KEY_ORG="SimpleEdu" 
export KEY_EMAIL="simpleedu@simple.com" export KEY_OU="MyOrganizationalUnit" 
```

![1713368291592](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713368291592.png)

使配置的环境变量生效

```autoit
[root@vpn1 ~]# cd /etc/openvpn/easy-rsa/2.0/ 
[root@vpn1 2.0]# source vars 
```

![1713368413677](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713368413677.png)

根据提示先删除所有，再根据自己情况进行修改（默认回车即可）

```bash
./clean-all
./build-ca
```

![1713368631625](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713368631625.png)

建服务端的证书 创建通用名(common name)为”server”的证书文件,交互输入自己的值,回车键进行，在提示输入密码的地方，设置一个密码如simple123

```autoit
[root@vpn1 2.0]# ./build-key-server server 
```

![1713368744633](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713368744633.png)

生成防攻击的key文件（防DDos攻击、UDP淹没等恶意攻击）

```vim
[root@vpn1 2.0]# openvpn --genkey --secret keys/ta.key 
[root@vpn1 2.0]# ll keys/ta.key 
```

![1713368924258](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713368924258.png)

建客户端证书 6.1.创建密钥文件，耗时间一分钟左右

```autoit
[root@vpn1 2.0]# ./build-dh 
```

![1713368970492](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713368970492.png)

可以看到有一个dh2048.pem的文件产生

```awk
ll /etc/openvpn/easy-rsa/2.0/keys/dh2048.pem
```

![1713369104835](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713369104835.png)

拷贝密钥认证文件到配置文件目录下

```perl
[root@vpn1 2.0]# cd /etc/openvpn/easy-rsa/2.0/keys/ 
[root@vpn1 keys]# cp dh2048.pem ca.crt server.crt server.key ta.key /etc/openvpn 
[root@vpn1 keys]# ls /etc/openvpn/
```

![1713369403452](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713369403452.png)

创建一个通用名(common name)为 client的客户端证书，交互输入自己的值,默认回车键进行

```perl
[root@vpn1 keys]# cd .. 
[root@vpn1 2.0]# ./build-key client 
[root@vpn1 2.0]# ll keys/client.* 
```

![1713369574893](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713369574893.png)

![1713369610705](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713369610705.png)

### 启动并检查

启动openvpn服务并设置为开机自启动

```ruby
# 启动openvpn服务
[root@vpn1 ~]# systemctl start openvpn@server.service
# 设置开机自启动
[root@vpn1 ~]# systemctl enable openvpn@server.service
```

![1713369825903](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713369825903.png)

```ruby
# 查看状态
[root@vpn1 ~]# systemctl status openvpn@server.service
```

![1713370871199](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713370871199.png)

这里如果失败就尝试从配置环境变量的 `./clean-all`步骤开始重试

```autoit
# 检查是否启动
[root@vpn1 ~]# netstat -lntup | grep openvpn
```

```apache
# 如下所示表示正常启动
tcp        0      0 0.0.0.0:1194            0.0.0.0:*               LISTEN      8870/openvpn 
# 监听端口号可以不同
```

![1713371019785](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713371019785.png)

### 客户端（vpn2）登录测试

在客户端安装openvpn

```coffeescript
[root@vpn2 ~]# vim /etc/yum.repos.d/simple.repo
# 将 baseurl=http://192.168.50.50/yum 修改为 baseurl=file:///data/repos
[root@vpn2 ~]# yum clean all
[root@vpn2 ~]# yum install openvpn -y 
```

![1713371429254](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713371429254.png)

在vpn1端把生产文件拷贝到客户端

```perl
[root@vpn1 keys]# cd /etc/openvpn/easy-rsa/2.0/keys/ 
# 密码为Simplexue123 
[root@vpn1 keys]# scp ca.crt client.crt client.key ta.key 192.168.2.11:/etc/openvpn/client/ 
```

![1713371564803](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713371564803.png)

编辑客户端配置文件

```swift
[root@vpn2 ~]# vim /etc/openvpn/client/client.conf 
client 
dev tun 
proto tcp 
remote 192.168.1.11 1194 
resolv-retry infinite 
nobind 
persist-key 
persist-tun 
ca /etc/openvpn/client/ca.crt 
cert /etc/openvpn/client/client.crt 
key /etc/openvpn/client/client.key 
tls-auth /etc/openvpn/client/ta.key 1 
cipher AES-256-CBC 
verb 3 
mute 20 
[root@vpn2 ~]# cat /etc/openvpn/client/client.conf
```

![1713372529308](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713372529308.png)

启动openvpn客户端并挂后台运行，并可实时查看其日志。

```swift
[root@vpn2 client]# cd /etc/openvpn/client/ 
[root@vpn2 client]# openvpn /etc/openvpn/client/client.conf & 
```

![1713372192732](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713372192732.png)

查看网卡信息，得知已获取到ip（建议新开一个Xshell窗口来进行以后的操作）

```autoit
[root@vpn2 ~]# ip addr show tun0 
```

![1713372634421](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713372634421.png)

测试是否可使用

```autoit
[root@vpn2 client]# ping 10.8.0.1
```

 ![1713372746686](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713372746686.png)

openvpn nat配置

```autoit
[root@vpn1 ~]# iptables -t nat -A POSTROUTING -s 10.8.0.1/24 -j MASQUERADE
[root@vpn1 ~]# iptables -t nat -nvL
```

![1713372939055](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713372939055.png)

关闭服务

```autoit
[root@vpn1 ~]# pkill openvpn 
[root@vpn2 ~]# pkill openvpn 
```

## IPsecVPN原理及安装配置

### 调整配置文件和参数

调整内核参数，开启数据转发，关闭icmp重定向并使之生效(两台主机都要完成)

#### 将下面配置文件加入/etc/sysctl.conf

```ini
[root@vpn1 ~]# vim  /etc/sysctl.conf
net.ipv4.ip_forward = 1
net.ipv4.conf.default.rp_filter = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.eth0.accept_redirects = 0
net.ipv4.conf.eth0.send_redirects = 0
net.ipv4.conf.eth1.accept_redirects = 0
net.ipv4.conf.eth1.send_redirects = 0
net.ipv4.conf.lo.accept_redirects = 0
net.ipv4.conf.lo.send_redirects = 0
```

![1713375803150](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713375803150.png)

#### 使配置生效

```autoit
[root@vpn1 ~]# sysctl -p
```

![1713375872607](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713375872607.png)

在VPN2上也做以上操作

### 安装openswan、libreswan并验证安装

```coffeescript
[root@vpn1 ~]# vim /etc/yum.repos.d/simple.repo
# 将 baseurl=http://192.168.50.50/yum 修改为 baseurl=file:///data/repos
[root@vpn1 ~]# yum clean all
# 如果无法安装检查上面的镜像源配置
[root@vpn1 ~]# yum install openswan libreswan  -y
[root@vpn1 ~]# ipsec --version
```

![1713376244775](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713376244775.png)

![1713376288524](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713376288524.png)

启动服务看是否正常，显示如图测正常，若不是请检查内核配置文件，两台机器都验证

```autoit
[root@vpn1 ~]# systemctl start ipsec.service
[root@vpn1 ~]# ipsec verify
```

![1713376377114](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713376377114.png)

```autoit
[root@vpn1 ~]# netstat -lntup | grep pluto 
```

 openswan监听在UDP的500和4500两个端口，其中500是用来IKE密钥交换协商，4500的NAT-T是nat穿透的

![1713376564165](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713376564165.png)

### 配置ipsecVPN配置（模式为network-to-network）

下面介绍两种认证方式

#### 基于pre-shared keys认证方式（PSK）

 配置/etc/ipsec.conf配置文件末尾增加如下（VPN1和VPN2的配置文件相同）

```routeros
conn net-to-net
ike=aes256-sha2_256;modp2048
    phase2alg=aes256-sha2_256;modp2048
    # 使用预共享密钥方式进行认证
    authby=secret
    type=tunnel
    # 一端IP地址
    left=192.168.1.11
    # 一端内网网段地址
    leftsubnet=10.0.0.0/24
    # 一端的标识符，可以任意填写，如果多个连接需要区分
    leftid=@vpn1
    leftnexthop=%defaultroute
    right=192.168.2.11
    rightsubnet=10.0.1.0/24
    rightid=@vpn2
    rightnexthop=%defaultroute
    # add代表只是添加，但并不会连接，如果为start则代表着启动自动连接
    auto=add
```

两台机器是基于密码来配置的，修改VPN1和VPN2的密码配置文件

##### VPN1

```accesslog
[root@vpn1 ~]# cat /etc/ipsec.secrets 
include /etc/ipsec.d/*.secrets
192.168.1.11 %any 0.0.0.0 : PSK "123"
```

##### VPN2

```accesslog
[root@vpn2 ~]# cat /etc/ipsec.secrets 
include /etc/ipsec.d/*.secrets
192.168.2.11 %any 0.0.0.0 : PSK "123"
```

![1713515780472](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713515780472.png)

##### 两端重新启动服务，并验证。

###### VPN1

```autoit
[root@vpn1 ~]# systemctl restart   ipsec.service
[root@vpn1 ~]# ipsec auto --up net-to-net
```

###### VPN2

```autoit
[root@vpn2 ~]# systemctl restart   ipsec.service
[root@vpn2 ~]# ipsec auto --up net-to-net
```

必须两台都执行，否则不能成功。
显示IPsec SA established tunnel mode 表示连接成功

![1713518145004](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713518145004.png)

##### 测试

由于只有两台机器，我们搭建虚拟内网网络来测试。

###### 在VPN1上搭建虚拟网络10.0.0.1/24 （步骤了解即可）

```routeros
ip link add left1 type veth peer name left2 
ip netns add left 
ip link set left1 netns left 
ip link set left2 up 
ip addr add dev left2 10.0.0.1/24 
ip netns exec left ip link set lo up 
ip netns exec left ip link set left1 up 
ip netns exec left ip addr add dev left1 10.0.0.2/24 
ip netns exec left ip route add default via 10.0.0.1  
# 查看虚拟网络，可知绑定IP为10.0.0.2 
ip netns exec left ip a 
```

![1713523810532](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713523810532.png)

###### 在VPN2上搭建虚拟网络10.0.1.1/24 （步骤了解即可）

```routeros
ip link add left1 type veth peer name left2 
ip netns add left 
ip link set left1 netns left 
ip link set left2 up 
ip addr add dev left2 10.0.1.1/24 
ip netns exec left ip link set lo up 
ip netns exec left ip link set left1 up 
ip netns exec left ip addr add dev left1 10.0.1.2/24 
ip netns exec left ip route add default via 10.0.1.1  
# 查看虚拟网络，可知绑定IP为10.0.1.2 
ip netns exec left ip a 
```

![1713523833336](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713523833336.png)

在VPN1上PING测试，可见可以ping通 `ip netns exec left ping 10.0.1.2 `

![1713523876906](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713523876906.png)

在VPN1和VPN2上清除虚拟内网，停止服务。两台机器都执行。

```coffeescript
[root@vpn1 ~]# ip netns del left 
[root@vpn1 ~]# systemctl stop ipsec 
```

## 云计算中基于Overlay技术的隧道网络实现

### 在VPN1和VPN2分别安装openvswitch并启动服务

安装openvswitch

```coffeescript
[root@vpn1 ~]# yum install openvswitch -y
```

![1713524249156](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713524249156.png)

启动服务

```autoit
[root@vpn1 ~]# systemctl start openvswitch.service
```

查看服务状态

```autoit
[root@vpn1 ~]# systemctl status openvswitch.service
```

![1713524334956](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713524334956.png)

### 配置VPN1

在VPN1上添加名为br0的网桥：

```smali
ovs-vsctl add-br br0
```

给br0网桥分配一个ip

```apache
ifconfig br0 10.1.0.1/24 up
```

![1713524497880](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713524497880.png)

### 配置VPN2

在VPN1上添加名为br0的网桥：

```smali
ovs-vsctl add-br br0
```

给br0网桥分配一个ip

```apache
ifconfig br0 10.1.0.2/24 up
```

![1713524572738](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713524572738.png)

### 搭建VXLAN隧道

在VPN1上设置VXLAN，远端ip设置为VPN2能对外通信的br0的ip。

```smali
ovs-vsctl add-port br0 vx1 -- set interface vx1 type=vxlan options:remote_ip=192.168.2.11
```

查看

```dart
ovs-vsctl show
```

![1713524727853](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713524727853.png)

在vpn2上设置VXLAN，远端ip设置为Host1能对外通信的br0的ip。

```smali
ovs-vsctl add-port br0 vx1 -- set interface vx1 type=vxlan options:remote_ip=192.168.1.11
```

查看

```dart
ovs-vsctl show
```

![1713524796773](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713524796773.png)

### 验证

验证VxLAN隧道 在VPN1上ping 10.1.0.2 发现可以通

![1713524832705](/image/%E7%BD%91%E7%BB%9C%E5%AE%89%E5%85%A8VPN%E5%AE%9E%E9%AA%8C/1713524832705.png)
