# 临时合成输入（未求解）

下面只是实际测试源文本的审阅副本，不是求解启动器。实例INP只存在于显式临时目录；本轮没有把它交给Abaqus。

```text
*HEADING
Restricted synthetic truss
*NODE
1,0,0,0
2,1,0,0
*ELEMENT, TYPE=T3D2, ELSET=BAR
1,1,2
*MATERIAL, NAME=STEEL
*ELASTIC
210000,0.3
*SOLID SECTION, ELSET=BAR, MATERIAL=STEEL
1.0
*STEP
*STATIC
0.1,1,1e-5,0.1
*BOUNDARY
1,1,3,0
2,2,3,0
*CLOAD
2,1,1
*END STEP
```

拒绝输入：`*NODE, INPUT=external.inp`；未知参数在读取external.inp前拒绝。
