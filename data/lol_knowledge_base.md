# 英雄联盟知识库数据文档

> **Schema版本**: 1.0 | **领域**: league_of_legends | **语言**: zh-CN
> **游戏版本**: 26.9 | **最后更新**: 2026-05-03
> **文档总数**: 20 | **文档类型**: hero_profile, ability_guide, build_guide, matchup_analysis, gameplay_guide, item_reference, rune_reference

---

## 📚 目录

- [1. 知识库Schema说明](#1-知识库schema说明)
- [2. 文档类型定义](#2-文档类型定义)
- [3. 文档列表](#3-文档列表)
- [4. 完整文档数据](#4-完整文档数据)
- [5. AI/RAG使用指南](#5-airag使用指南)

---

## 1. 知识库Schema说明

### 1.1 顶层结构

```json
{
  "schema_version": "string (semver)",
  "domain": "string (领域标识)",
  "language": "string (语言代码)",
  "last_updated": "string (YYYY-MM-DD)",
  "game_version": "string",
  "total_documents": "integer",
  "document_types": ["string"],
  "documents": [Document]
}
```

### 1.2 文档结构（Document）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| doc_id | string | 是 | 文档唯一标识，格式：`type_hero_topic` |
| doc_type | string | 是 | 文档类型，见下表 |
| hero_id | string | 条件 | 关联英雄英文ID（英雄相关文档必填） |
| hero_name | string | 条件 | 关联英雄中文名 |
| title | string | 否 | 英雄称号（仅hero_profile） |
| roles | array | 否 | 英雄位置（仅hero_profile） |
| primary_role | string | 否 | 主要位置（仅hero_profile） |
| resource | string | 否 | 资源类型（仅hero_profile） |
| attack_type | string | 否 | 攻击类型（仅hero_profile） |
| adaptive_type | string | 否 | 自适应属性（仅hero_profile） |
| difficulty | int | 否 | 难度评级（仅hero_profile） |
| ability_key | string | 否 | 技能按键（仅ability_guide） |
| ability_name | string | 否 | 技能名称（仅ability_guide） |
| role | string | 否 | 位置/路线（仅build_guide） |
| topic | string | 否 | 主题（仅gameplay_guide） |
| hero_a | string | 否 | 对位英雄A ID（仅matchup_analysis） |
| hero_a_name | string | 否 | 对位英雄A名称 |
| hero_b | string | 否 | 对位英雄B ID |
| hero_b_name | string | 否 | 对位英雄B名称 |
| item_name | string | 否 | 装备名称（仅item_reference） |
| item_category | string | 否 | 装备分类（仅item_reference） |
| rune_name | string | 否 | 符文名称（仅rune_reference） |
| rune_tree | string | 否 | 符文系（仅rune_reference） |
| rune_type | string | 否 | 符文类型（仅rune_reference） |
| content | string | 是 | 文档正文内容（知识库核心） |
| keywords | array | 是 | 关键词标签，用于检索和过滤 |
| embedding_text | string | 是 | 向量化文本，用于语义检索 |

### 1.3 文档类型枚举

| 类型 | 说明 | 核心字段 |
|------|------|----------|
| hero_profile | 英雄档案 | hero_id, name, title, roles, stats_summary |
| ability_guide | 技能详解 | hero_id, ability_key, ability_name, mechanics |
| build_guide | 出装符文 | hero_id, role, runes, items, skill_order |
| matchup_analysis | 对位分析 | hero_a, hero_b, role, win_rate, counter_strategy |
| gameplay_guide | 游戏策略 | hero_id, topic, phase, tactics |
| item_reference | 装备参考 | item_name, category, stats, effects |
| rune_reference | 符文参考 | rune_name, tree, type, mechanics |

---

## 2. 文档类型定义

### 2.1 hero_profile（英雄档案）

包含英雄的完整定位、属性概览、技能机制和核心玩法。用于回答"这个英雄怎么玩"、"亚索是什么定位"等问题。

**embedding_text构建规则**：`hero_name title attack_type adaptive_type primary_role resource 核心机制关键词`

### 2.2 ability_guide（技能详解）

单个技能的深度解析，包括数值、机制、技巧和连招。用于回答"亚索Q技能怎么用"、"铁男R能解吗"等问题。

**embedding_text构建规则**：`hero_name ability_name ability_key技能 机制关键词`

### 2.3 build_guide（出装符文）

特定位置的完整出装和符文配置。用于回答"亚索中路怎么出装"、"薇恩带什么符文"等问题。

**embedding_text构建规则**：`hero_name role 出装 符文 核心装备/符文`

### 2.4 matchup_analysis（对位分析）

两个英雄的对位关系、胜率、克制关系和应对策略。用于回答"亚索怎么打玛尔扎哈"、"谁counter诺手"等问题。

**embedding_text构建规则**：`hero_a_name hero_b_name role对位 胜负关系`

### 2.5 gameplay_guide（游戏策略）

特定主题的游戏策略（团战、打野路线、对线等）。用于回答"亚索团战怎么打"、"魔腾怎么刷野"等问题。

**embedding_text构建规则**：`hero_name topic 策略 关键词`

### 2.6 item_reference（装备参考）

单件装备的属性、效果和适用场景。用于回答"不朽盾弓适合谁"、"裂隙制造者什么效果"等问题。

**embedding_text构建规则**：`item_name category 属性关键词 适用英雄`

### 2.7 rune_reference（符文参考）

单个符文的机制和适用英雄。用于回答"征服者适合谁"、"致命节奏和强攻哪个好"等问题。

**embedding_text构建规则**：`rune_name rune_tree rune_type 机制关键词`

---

## 3. 文档列表

### 英雄档案 (6篇)

| 文档ID | 标题/主题 | 关键词 |
|--------|-----------|--------|
| hero_yasuo_profile | 亚索 (疾风剑豪) | 亚索, 疾风剑豪, 暴击, 击飞, 风墙, 中路, 上路, 刺客, 战士 |
| hero_morde_profile | 莫德凯撒 (铁铠冥魂) | 莫德凯撒, 铁铠冥魂, 法坦, 上单, 死亡领域, 光环, 单挑 |
| hero_nocturne_profile | 魔腾 (永恒梦魇) | 魔腾, 永恒梦魇, 打野, 刺客, 大招突进, 恐惧, 关灯 |
| hero_malzahar_profile | 玛尔扎哈 (虚空先知) | 玛尔扎哈, 虚空先知, 法师, 中路, 压制, 护盾, 清线, 控制 |
| hero_vayne_profile | 薇恩 (暗夜猎手) | 薇恩, 暗夜猎手, ADC, 下路, 真实伤害, 隐身, 坦克杀手, 后期 |
| hero_pyke_profile | 派克 (血港鬼影) | 派克, 血港鬼影, 辅助, 刺客, 赏金, 处决, 游走 |

### 技能详解 (3篇)

| 文档ID | 标题/主题 | 关键词 |
|--------|-----------|--------|
| ability_yasuo_q | 亚索 - 斩钢闪 (Q) | 亚索, 斩钢闪, Q技能, 旋风, 击飞, 连招 |
| ability_morde_r | 莫德凯撒 - 死亡领域 (R) | 莫德凯撒, 死亡领域, R技能, 单挑, 隔离, 属性窃取 |
| ability_nocturne_r | 魔腾 - 鬼影重重 (R) | 魔腾, 鬼影重重, R技能, 关灯, 突进, gank, 开团 |

### 出装符文 (3篇)

| 文档ID | 标题/主题 | 关键词 |
|--------|-----------|--------|
| build_yasuo_mid | 亚索 - Mid | 亚索, 中路, 出装, 符文, 致命节奏, 不朽盾弓, 无尽之刃 |
| build_morde_top | 莫德凯撒 - Top | 莫德凯撒, 上单, 出装, 符文, 征服者, 裂隙制造者, 法坦 |
| build_vayne_bot | 薇恩 - Bot | 薇恩, 下路, ADC, 出装, 符文, 强攻, 海妖杀手, 真实伤害 |

### 对位分析 (2篇)

| 文档ID | 标题/主题 | 关键词 |
|--------|-----------|--------|
| matchup_yasuo_vs_malzahar | 亚索 vs 玛尔扎哈 | 亚索, 玛尔扎哈, 对位, 中路, 压制, 水银, 劣势 |
| matchup_morde_vs_darius | 莫德凯撒 vs 德莱厄斯 | 莫德凯撒, 德莱厄斯, 诺手, 对位, 上单, 血怒, 死亡领域 |

### 游戏策略 (2篇)

| 文档ID | 标题/主题 | 关键词 |
|--------|-----------|--------|
| gameplay_yasuo_teamfight | 亚索 - teamfight | 亚索, 团战, 击飞, 风墙, 进场, 侧翼, 刺客 |
| gameplay_jungle_pathing | 魔腾 - jungle_pathing | 魔腾, 打野, 刷野路线, gank, 控龙, 反野, 速6 |

### 装备参考 (2篇)

| 文档ID | 标题/主题 | 关键词 |
|--------|-----------|--------|
| item_immortal_shieldbow | 不朽盾弓 | 不朽盾弓, 神话装备, ADC, 护盾, 暴击, 吸血 |
| item_riftmaker | 裂隙制造者 | 裂隙制造者, 神话装备, 法坦, 全能吸血, 真实伤害, 持续输出 |

### 符文参考 (2篇)

| 文档ID | 标题/主题 | 关键词 |
|--------|-----------|--------|
| rune_conqueror | 征服者 | 征服者, 精密, 基石符文, 战士, 续航, 自适应之力 |
| rune_lethal_tempo | 致命节奏 | 致命节奏, 精密, 基石符文, 攻速, ADC, 突破上限 |

---

## 4. 完整文档数据

### hero_yasuo_profile

```json
{
  "doc_id": "hero_yasuo_profile",
  "doc_type": "hero_profile",
  "hero_id": "Yasuo",
  "hero_name": "亚索",
  "title": "疾风剑豪",
  "roles": [
    "Top",
    "Mid"
  ],
  "primary_role": "Mid",
  "resource": "无消耗",
  "attack_type": "近战",
  "adaptive_type": "物理",
  "difficulty": 3,
  "content": "亚索是英雄联盟中的近战物理刺客/战士，主打中路和上路。核心机制围绕暴击和击飞展开。\n\n基础属性：生命值590(+101/级)，攻击力60(+3.4/级)，护甲30(+4.6/级)，魔抗32(+2.05/级)，攻击速度0.697(+2.5%/级)，移动速度345，射程175。\n\n技能概览：\n- 被动浪客之道：暴击几率翻倍，移动时积攒护盾\n- Q斩钢闪：向前突刺，第三次释放形成旋风可击飞敌人\n- W风之障壁：阻挡所有敌方飞行道具\n- E踏前斩：向目标敌人突进，可叠加伤害\n- R狂风绝息斩：对击飞敌人造成巨额伤害并延长击飞时间\n\n核心玩法：利用Q积攒旋风，配合队友或自身击飞接R开团。风墙可阻挡关键技能如女警R、金克丝R等。E技能在兵线中灵活穿梭躲避技能。",
  "keywords": [
    "亚索",
    "疾风剑豪",
    "暴击",
    "击飞",
    "风墙",
    "中路",
    "上路",
    "刺客",
    "战士"
  ],
  "embedding_text": "亚索 疾风剑豪 近战物理刺客 中路 上路 暴击 击飞 风墙 无消耗"
}
```

---

### hero_morde_profile

```json
{
  "doc_id": "hero_morde_profile",
  "doc_type": "hero_profile",
  "hero_id": "Mordekaiser",
  "hero_name": "莫德凯撒",
  "title": "铁铠冥魂",
  "roles": [
    "Top"
  ],
  "primary_role": "Top",
  "resource": "无消耗",
  "attack_type": "近战",
  "adaptive_type": "法术",
  "difficulty": 2,
  "content": "莫德凯撒是法坦型上单英雄，通过被动光环和R技能死亡领域制造持续输出和单挑优势。\n\n基础属性：生命值645(+104/级)，攻击力61(+4.0/级)，护甲37(+4.2/级)，魔抗32(+2.05/级)，攻击速度0.694(+1.0%/级)，移动速度335，射程175。\n\n技能概览：\n- 被动幽冥起兮：普攻造成额外魔法伤害，叠满后生成持续伤害光环\n- Q破灭之锤：对单体目标造成高额AP伤害\n- W不坏之身：储存伤害转化为护盾和治疗\n- E断魂一扼：拉取敌人并造成伤害\n- R死亡领域：将目标拖入异次元单挑7秒，击杀后窃取属性\n\n核心玩法：利用被动换血，Q单体爆发高。R技能可隔离敌方核心输出（如ADC或打野），在领域中击杀后获得永久属性加成。适合对抗缺乏位移的坦克和战士。",
  "keywords": [
    "莫德凯撒",
    "铁铠冥魂",
    "法坦",
    "上单",
    "死亡领域",
    "光环",
    "单挑"
  ],
  "embedding_text": "莫德凯撒 铁铠冥魂 近战法术坦克 上单 无消耗 死亡领域 单挑"
}
```

---

### hero_nocturne_profile

```json
{
  "doc_id": "hero_nocturne_profile",
  "doc_type": "hero_profile",
  "hero_id": "Nocturne",
  "hero_name": "魔腾",
  "title": "永恒梦魇",
  "roles": [
    "Jungle"
  ],
  "primary_role": "Jungle",
  "resource": "法力值",
  "attack_type": "近战",
  "adaptive_type": "物理",
  "difficulty": 2,
  "content": "魔腾是依赖6级大招的物理刺客型打野，通过R技能全图突进gank和开团。\n\n基础属性：生命值585(+95/级)，法力值300(+40/级)，攻击力62(+3.1/级)，护甲36(+4.2/级)，魔抗32(+1.25/级)，攻击速度0.721(+2.7%/级)，移动速度345，射程125。\n\n技能概览：\n- 被动暗影之刃：周期性普攻造成AOE伤害并回血\n- Q梦魇之径：释放暗影路径，在路径上获得加速和额外攻击力\n- W黑暗庇护：被动加攻速，主动抵挡一次技能\n- E无言恐惧：对目标造成恐惧和伤害\n- R鬼影重重：减少所有敌方视野，可突进至目标造成高额伤害\n\n核心玩法：前期快速清野到6级，6级后利用R发起gank。团战侧翼切入，优先击杀无位移的ADC和法师。W技能时机决定生死，可抵挡关键控制。",
  "keywords": [
    "魔腾",
    "永恒梦魇",
    "打野",
    "刺客",
    "大招突进",
    "恐惧",
    "关灯"
  ],
  "embedding_text": "魔腾 永恒梦魇 近战物理刺客 打野 法力值 大招突进 恐惧"
}
```

---

### hero_malzahar_profile

```json
{
  "doc_id": "hero_malzahar_profile",
  "doc_type": "hero_profile",
  "hero_id": "Malzahar",
  "hero_name": "玛尔扎哈",
  "title": "虚空先知",
  "roles": [
    "Mid"
  ],
  "primary_role": "Mid",
  "resource": "法力值",
  "attack_type": "远程",
  "adaptive_type": "法术",
  "difficulty": 1,
  "content": "玛尔扎哈是远程控制型法师，以稳定的点控和清线能力著称，是对抗刺客的优选。\n\n基础属性：生命值580(+101/级)，法力值375(+60/级)，攻击力55(+3.0/级)，护甲18(+4.0/级)，魔抗30(+1.3/级)，攻击速度0.625(+1.5%/级)，移动速度335，射程500。\n\n技能概览：\n- 被动虚空穿越：周期性获得护盾，免疫控制和伤害\n- Q虚空召唤：召唤虚空裂隙造成沉默和伤害\n- W虚空swarm：召唤虚灵协助作战\n- E煞星幻象：对目标施加持续伤害，击杀后传染\n- R冥府之握：压制目标2.5秒并造成持续伤害\n\n核心玩法：利用E技能快速清线，被动护盾防止gank。R技能是游戏最强单体控制之一，可完全压制刺客突进。团战优先R敌方核心输出或刺客。",
  "keywords": [
    "玛尔扎哈",
    "虚空先知",
    "法师",
    "中路",
    "压制",
    "护盾",
    "清线",
    "控制"
  ],
  "embedding_text": "玛尔扎哈 虚空先知 远程法术法师 中路 法力值 压制 护盾 清线"
}
```

---

### hero_vayne_profile

```json
{
  "doc_id": "hero_vayne_profile",
  "doc_type": "hero_profile",
  "hero_id": "Vayne",
  "hero_name": "薇恩",
  "title": "暗夜猎手",
  "roles": [
    "Bot"
  ],
  "primary_role": "Bot",
  "resource": "法力值",
  "attack_type": "远程",
  "adaptive_type": "物理",
  "difficulty": 3,
  "content": "薇恩是后期最强ADC之一，通过W技能真实伤害和Q技能隐身机制克制坦克阵容。\n\n基础属性：生命值545(+103/级)，法力值231(+35/级)，攻击力60(+2.36/级)，护甲23(+4.6/级)，魔抗30(+1.3/级)，攻击速度0.658(+3.3%/级)，移动速度330，射程550。\n\n技能概览：\n- 被动暗夜猎手：朝敌方英雄移动时获得移速加成\n- Q闪避突袭：翻滚并强化下次普攻，大招期间获得隐身\n- W圣银弩箭：每第三次攻击造成基于目标最大生命值的真实伤害\n- E恶魔审判：击退目标，撞墙则眩晕\n- R终极时刻：获得攻击力加成，Q技能隐身\n\n核心玩法：前期极弱，专注发育。两件套后开始发力，三件套后成为最强ADC。团战侧翼输出，利用Q调整位置，E技能保命。真实伤害使其成为坦克杀手。",
  "keywords": [
    "薇恩",
    "暗夜猎手",
    "ADC",
    "下路",
    "真实伤害",
    "隐身",
    "坦克杀手",
    "后期"
  ],
  "embedding_text": "薇恩 暗夜猎手 远程物理ADC 下路 法力值 真实伤害 隐身 后期"
}
```

---

### hero_pyke_profile

```json
{
  "doc_id": "hero_pyke_profile",
  "doc_type": "hero_profile",
  "hero_id": "Pyke",
  "hero_name": "派克",
  "title": "血港鬼影",
  "roles": [
    "Support"
  ],
  "primary_role": "Support",
  "resource": "法力值",
  "attack_type": "近战",
  "adaptive_type": "物理",
  "difficulty": 3,
  "content": "派克是物理刺客型辅助，通过高爆发和R技能赏金分享机制滚雪球。\n\n基础属性：生命值600(+100/级)，法力值415(+50/级)，攻击力62(+2.0/级)，护甲47(+4.5/级)，魔抗32(+2.05/级)，攻击速度0.669(+2.5%/级)，移动速度330，射程150。\n\n技能概览：\n- 被动溺水之幸：损失生命转化为灰色生命，脱战后回复\n- Q透骨尖钉：可瞬发或蓄力投掷，命中后拉回敌人\n- W幽潭潜行：进入伪装状态并加速\n- E魅影浪洄：位移并留下幻影，延迟后幻影返回眩晕路径敌人\n- R涌泉之恨：X型斩击，处决低血量敌人并分享赏金\n\n核心玩法：前期利用Q和E控制找机会击杀，W游走支援。R技能处决后赏金分享给队友，经济滚雪球能力强。团战绕后切入，优先斩杀残血。",
  "keywords": [
    "派克",
    "血港鬼影",
    "辅助",
    "刺客",
    "赏金",
    "处决",
    "游走"
  ],
  "embedding_text": "派克 血港鬼影 近战物理刺客 辅助 法力值 赏金 处决 游走"
}
```

---

### ability_yasuo_q

```json
{
  "doc_id": "ability_yasuo_q",
  "doc_type": "ability_guide",
  "hero_id": "Yasuo",
  "hero_name": "亚索",
  "ability_key": "Q",
  "ability_name": "斩钢闪",
  "content": "亚索Q技能斩钢闪详解：\n\n机制：向前突刺，对首个命中的敌人造成伤害。命中目标后获得一层旋风烈斩效果，持续6秒。积攒2层后，下次斩钢闪将形成一道旋风，击飞路径上的所有敌人0.75秒。\n\n数值：基础伤害20/45/70/95/120，AD加成100%。冷却时间4秒（受攻速影响，最低1.33秒）。\n\n技巧：\n1. Q可以暴击，享受暴击伤害加成\n2. 旋风的击飞可以配合大招狂风绝息斩\n3. 在E技能突进过程中可以释放Q，形成环形斩击\n4. Q被视为普攻，可触发攻击特效\n5. 最低冷却1.33秒，高攻速下可频繁释放\n\n连招：EQ（环形斩击）→ 攒旋风 → Q3击飞 → R狂风绝息斩\n\n克制关系：可被风墙阻挡的飞行道具克制，但Q本身不是飞行道具",
  "keywords": [
    "亚索",
    "斩钢闪",
    "Q技能",
    "旋风",
    "击飞",
    "连招"
  ],
  "embedding_text": "亚索 斩钢闪 Q技能 旋风 击飞 连招 暴击 环形斩击"
}
```

---

### ability_morde_r

```json
{
  "doc_id": "ability_morde_r",
  "doc_type": "ability_guide",
  "hero_id": "Mordekaiser",
  "hero_name": "莫德凯撒",
  "ability_key": "R",
  "ability_name": "死亡领域",
  "content": "莫德凯撒R技能死亡领域详解：\n\n机制：将目标英雄拖入死亡领域7秒，期间双方都无法被外界选中或影响。击杀目标后，莫德凯撒获得目标10%的核心属性（攻击力、法强、攻速、护甲、魔抗）直到目标复活。\n\n数值：冷却时间140/120/100秒。无基础伤害，效果为纯机制型。\n\n使用时机：\n1. 团战开始时隔离敌方核心输出（ADC、打野或中单）\n2. 被集火时R敌方辅助或坦克，避免被秒杀\n3. 龙团时R敌方打野，阻止其抢龙\n4. 1v1单挑时确保能击杀以窃取属性\n\n注意事项：\n- 水银饰带、米凯尔的祝福、清洁术可解除\n- 目标在领域内死亡，莫德凯撒获得属性加成\n- 领域内莫德凯撒获得额外属性加成\n- 可利用领域躲避敌方关键技能（如死歌R、金克丝R）\n\n克制英雄：缺乏位移的ADC（艾希、烬）、依赖队友保护的法师（泽拉斯、维克兹）",
  "keywords": [
    "莫德凯撒",
    "死亡领域",
    "R技能",
    "单挑",
    "隔离",
    "属性窃取"
  ],
  "embedding_text": "莫德凯撒 死亡领域 R技能 单挑 隔离 属性窃取 水银"
}
```

---

### ability_nocturne_r

```json
{
  "doc_id": "ability_nocturne_r",
  "doc_type": "ability_guide",
  "hero_id": "Nocturne",
  "hero_name": "魔腾",
  "ability_key": "R",
  "ability_name": "鬼影重重",
  "content": "魔腾R技能鬼影重重详解：\n\n机制：减少所有敌方英雄的视野范围，并移除彼此间的友方视野，持续6秒。期间可再次激活突进至目标英雄，造成物理伤害。\n\n数值：基础伤害150/250/350，AD加成120%。冷却时间140/120/100秒。突进范围2500/3250/4000。\n\n战术应用：\n1. Gank：6级后利用R发起gank，优先选择无位移英雄\n2. 开团：团战开始时R敌方后排，配合队友秒杀\n3. 反打：敌方开团后R其后排，形成前后包夹\n4. 抢龙：龙团时R敌方打野，阻止其进入龙坑\n\n配合英雄：\n- 强开团辅助（蕾欧娜、锤石）先手控制后R跟进\n- 全球流英雄（卡牌、慎）形成多路包夹\n\n反制手段：\n- 中亚沙漏：R突进过程中使用可躲避伤害\n- 闪现：R突进过程中闪现可打断\n- 女妖面纱：阻挡R的突进效果\n- 抱团：魔腾R单体突进，抱团可保护后排",
  "keywords": [
    "魔腾",
    "鬼影重重",
    "R技能",
    "关灯",
    "突进",
    "gank",
    "开团"
  ],
  "embedding_text": "魔腾 鬼影重重 R技能 关灯 突进 gank 开团 视野压制"
}
```

---

### build_yasuo_mid

```json
{
  "doc_id": "build_yasuo_mid",
  "doc_type": "build_guide",
  "hero_id": "Yasuo",
  "hero_name": "亚索",
  "role": "Mid",
  "content": "亚索中路出装与符文配置：\n\n符文配置：\n主系精密：致命节奏 → 凯旋 → 传说：欢欣 → 坚毅不倒\n副系主宰：血之滋味 → 贪欲猎手\n碎片：攻击速度 / 适应之力 / 魔法抗性\n\n出门装：多兰之刃 + 生命药水\n\n核心三件套：\n1. 不朽盾弓（神话）：提供护盾、暴击、吸血，被动救主灵刃保命\n2. 狂战士胫甲：攻速鞋，提升Q技能释放频率\n3. 无尽之刃：暴击伤害提升至225%，配合被动暴击翻倍\n\n完整六神装：不朽盾弓 → 狂战士胫甲 → 无尽之刃 → 死亡之舞 → 玛莫提乌斯之噬 → 守护天使\n\n备选装备：\n- 饮血剑：高额吸血和护盾\n- 凡性的提醒：对抗高回复阵容\n- 纳沃利迅刃：进一步减少Q冷却\n\n加点顺序：主Q副E，有R点R\n\n对线技巧：\n- 1级学Q，利用Q补刀和消耗\n- 3级后EQ连招换血\n- 攒旋风后寻找击飞机会配合打野gank\n- 风墙可阻挡敌方法师关键技能",
  "keywords": [
    "亚索",
    "中路",
    "出装",
    "符文",
    "致命节奏",
    "不朽盾弓",
    "无尽之刃"
  ],
  "embedding_text": "亚索 中路 出装 符文 致命节奏 不朽盾弓 无尽之刃 暴击"
}
```

---

### build_morde_top

```json
{
  "doc_id": "build_morde_top",
  "doc_type": "build_guide",
  "hero_id": "Mordekaiser",
  "hero_name": "莫德凯撒",
  "role": "Top",
  "content": "莫德凯撒上单出装与符文配置：\n\n符文配置：\n主系精密：征服者 → 凯旋 → 传说：韧性 → 坚毅不倒\n副系坚决：护盾猛击 → 复苏之风\n碎片：攻击速度 / 适应之力 / 护甲\n\n出门装：多兰之盾 + 生命药水\n\n核心三件套：\n1. 裂隙制造者（神话）：提供法强、生命值、全能吸血，被动虚空腐蚀提升持续伤害\n2. 瑞莱的冰晶节杖：法强+生命值，技能附加减速，黏人能力强\n3. 中娅沙漏：法强+护甲，主动金身躲避关键技能\n\n完整六神装：裂隙制造者 → 瑞莱的冰晶节杖 → 中娅沙漏 → 荆棘之甲 → 自然之力 → 石像鬼石板甲\n\n备选装备：\n- 恶魔之拥：对抗高血量坦克\n- 纳什之牙：提升攻速和普攻伤害\n- 虚空之杖：对抗高魔抗阵容\n\n加点顺序：主Q副W，有R点R\n\n对线技巧：\n- 利用被动换血，Q单体伤害极高\n- E技能可拉回逃跑的敌人或打断突进\n- R技能在敌方打野gank时使用，形成1v1单挑\n- 6级后R技能可用来躲避敌方大招（如诺手R、盖伦R）",
  "keywords": [
    "莫德凯撒",
    "上单",
    "出装",
    "符文",
    "征服者",
    "裂隙制造者",
    "法坦"
  ],
  "embedding_text": "莫德凯撒 上单 出装 符文 征服者 裂隙制造者 法坦 冰杖"
}
```

---

### build_vayne_bot

```json
{
  "doc_id": "build_vayne_bot",
  "doc_type": "build_guide",
  "hero_id": "Vayne",
  "hero_name": "薇恩",
  "role": "Bot",
  "content": "薇恩下路出装与符文配置：\n\n符文配置：\n主系精密：强攻 → 凯旋 → 传说：欢欣 → 砍倒\n副系主宰：血之滋味 → 贪欲猎手\n碎片：攻击速度 / 适应之力 / 护甲\n\n出门装：多兰之刃 + 生命药水\n\n核心三件套：\n1. 海妖杀手（神话）：每第三次攻击造成额外真实伤害，配合W双重真伤\n2. 狂战士胫甲：攻速鞋，提升输出频率\n3. 鬼索的狂暴之刃：将部分暴击转化为额外攻击特效伤害，配合W和神话被动\n\n完整六神装：海妖杀手 → 狂战士胫甲 → 鬼索的狂暴之刃 → 智慧末刃 → 守护天使 → 凡性的提醒\n\n备选装备：\n- 幻影之舞：攻速+暴击+移速+护盾\n- 饮血剑：高额吸血\n- 兰德里的苦楚：AP特效流（娱乐玩法）\n\n加点顺序：主W副Q，有R点R\n\n对线技巧：\n- 前期极弱，专注补刀发育，避免换血\n- 利用Q翻滚躲避敌方技能\n- E技能将敌人击退至墙体可眩晕\n- 6级后R+Q隐身可反打或逃生\n\n辅助搭配：\n- 强保护型：璐璐、风女、娜美\n- 强开团型：锤石、蕾欧娜（需沟通）",
  "keywords": [
    "薇恩",
    "下路",
    "ADC",
    "出装",
    "符文",
    "强攻",
    "海妖杀手",
    "真实伤害"
  ],
  "embedding_text": "薇恩 下路 ADC 出装 符文 强攻 海妖杀手 真实伤害 攻速"
}
```

---

### matchup_yasuo_vs_malzahar

```json
{
  "doc_id": "matchup_yasuo_vs_malzahar",
  "doc_type": "matchup_analysis",
  "hero_a": "Yasuo",
  "hero_a_name": "亚索",
  "hero_b": "Malzahar",
  "hero_b_name": "玛尔扎哈",
  "role": "Mid",
  "content": "亚索 vs 玛尔扎哈 中路对位分析：\n\n对位难度：★★★★☆（亚索劣势）\n胜率：亚索45% vs 玛尔扎哈55%\n\n核心矛盾：\n玛尔扎哈的R冥府之握是游戏最强单体控制（压制2.5秒），可完全打断亚索的突进和输出。亚索的风墙无法阻挡R技能（不是飞行道具）。\n\n对线阶段：\n- 1-5级：亚索有优势，利用Q和E消耗。注意玛尔扎哈E技能的传染清线\n- 6级后：玛尔扎哈获得R后亚索极难先手，被动护盾可抵挡一次Q或E\n- 玛尔扎哈清线快，亚索易被锁在中路无法支援\n\n应对策略：\n1. 出水银饰带或水银之靴解除R压制\n2. 呼叫打野gank，玛尔扎哈缺乏位移，gank成功率高\n3. 利用兵线E技能灵活走位，避免被E+R连招\n4. 团战侧翼切入，避免被R直接压制\n\n关键装备：水银饰带（1300金）是必出装备，优先级高于核心装\n\n符文调整：副系可带坚决系骸骨镀层+复苏，提升换血能力",
  "keywords": [
    "亚索",
    "玛尔扎哈",
    "对位",
    "中路",
    "压制",
    "水银",
    "劣势"
  ],
  "embedding_text": "亚索 玛尔扎哈 中路对位 劣势 压制 水银 对位分析"
}
```

---

### matchup_morde_vs_darius

```json
{
  "doc_id": "matchup_morde_vs_darius",
  "doc_type": "matchup_analysis",
  "hero_a": "Mordekaiser",
  "hero_a_name": "莫德凯撒",
  "hero_b": "Darius",
  "hero_b_name": "德莱厄斯",
  "role": "Top",
  "content": "莫德凯撒 vs 德莱厄斯 上路对位分析：\n\n对位难度：★★★☆☆（均势偏优）\n胜率：莫德凯撒52% vs 德莱厄斯48%\n\n核心矛盾：\n德莱厄斯（诺手）是线霸级战士，血怒机制使其持续作战极强。莫德凯撒的R死亡领域可隔离诺手，避免其叠满血怒，同时窃取属性。\n\n对线阶段：\n- 1-5级：诺手强势，莫德凯撒应猥琐发育，利用Q补刀\n- 6级后：莫德凯撒R可规避诺手血怒高潮期，在领域中击杀后获得属性加成\n- 诺手缺乏位移，莫德凯撒E容易命中\n\n应对策略：\n1. 避免被诺手外圈Q命中（回血+血怒）\n2. 诺手拉人（E）后反用E拉回，打断其连招\n3. 6级后R技能在诺手叠满血怒前使用，避免被斩杀\n4. 第一件出荆棘之甲克制诺手回血\n\n装备优先级：荆棘之甲 > 裂隙制造者\n\n团战差异：\n- 诺手：收割型，依赖血怒和R斩杀\n- 莫德凯撒：开团型，R隔离敌方核心",
  "keywords": [
    "莫德凯撒",
    "德莱厄斯",
    "诺手",
    "对位",
    "上单",
    "血怒",
    "死亡领域"
  ],
  "embedding_text": "莫德凯撒 德莱厄斯 诺手 上单对位 均势 死亡领域 血怒"
}
```

---

### gameplay_yasuo_teamfight

```json
{
  "doc_id": "gameplay_yasuo_teamfight",
  "doc_type": "gameplay_guide",
  "hero_id": "Yasuo",
  "hero_name": "亚索",
  "topic": "teamfight",
  "content": "亚索团战策略详解：\n\n定位：侧翼切入型刺客/战士，依赖击飞开团\n\n进场时机：\n1. 等待队友先手击飞（蕾欧娜R、石头人R、酒桶E等）\n2. 自行积攒Q3旋风，寻找角度击飞多人\n3. 敌方关键控制技能交完后进场\n\n核心操作：\n- 风墙（W）放置位置决定团战走向，应阻挡敌方ADC和法师的飞行道具\n- R技能可延长击飞时间1秒，为队友创造输出窗口\n- R后获得50%护甲穿透，优先攻击高护甲目标\n- E技能在敌方单位和兵线间穿梭，调整输出位置\n\n危险情况：\n- 敌方有玛尔扎哈、蝎子等强控英雄时，需等待其控制技能交出\n- 敌方有波比、薇恩等击退英雄时，注意进场角度\n- 避免在敌方塔下强行接R\n\n装备联动：\n- 不朽盾弓被动触发时，可大胆进场吸收伤害\n- 守护天使提供二次进场机会\n- 死亡之舞将爆发伤害转化为流血，提升生存\n\n最佳队友：石头人、酒桶、奥恩、蕾欧娜、牛头",
  "keywords": [
    "亚索",
    "团战",
    "击飞",
    "风墙",
    "进场",
    "侧翼",
    "刺客"
  ],
  "embedding_text": "亚索 团战策略 击飞 风墙 进场 侧翼 护甲穿透"
}
```

---

### gameplay_jungle_pathing

```json
{
  "doc_id": "gameplay_jungle_pathing",
  "doc_type": "gameplay_guide",
  "hero_id": "Nocturne",
  "hero_name": "魔腾",
  "topic": "jungle_pathing",
  "content": "魔腾打野路线与Gank时机：\n\n标准刷野路线（蓝方）：\n1. 红BUFF开局（焰爪猫幼崽）\n2. 石甲虫 → 锋喙鸟 → 狼群\n3. 蓝BUFF + 魔沼蛙\n4. 河蟹（3:30刷新）\n5. 到达4级，观察线上情况\n\n速6路线：\n- 全清野区，跳过河蟹\n- 4分30秒左右到达6级\n- 第一个R选择最优路进行gank\n\nGank优先级：\n1. 无位移ADC（艾希、烬、金克丝）\n2. 压线过深的边路\n3. 半血以下的残血目标\n4. 有队友控制的线路\n\nR技能使用原则：\n- 不用于清线或赶路（除非紧急支援）\n- Gank时确保目标无闪现或已使用过\n- 龙团前30秒保留R，用于抢龙或阻止敌方打野\n- 敌方抱团时避免强行R进场（易被集火）\n\n反野时机：\n- 敌方打野出现在其他路时，入侵其野区\n- 优先偷取石甲虫和锋喙鸟（经验高）\n- 放置视野后及时撤退，避免遭遇战\n\n控龙节奏：\n- 第一条龙（3:30）可放弃，专注速6\n- 6级后利用R控龙，R敌方打野阻止抢龙\n- 峡谷先锋优先于小龙（帮助推塔）",
  "keywords": [
    "魔腾",
    "打野",
    "刷野路线",
    "gank",
    "控龙",
    "反野",
    "速6"
  ],
  "embedding_text": "魔腾 打野路线 gank 控龙 反野 速6 刷野"
}
```

---

### item_immortal_shieldbow

```json
{
  "doc_id": "item_immortal_shieldbow",
  "doc_type": "item_reference",
  "item_name": "不朽盾弓",
  "item_category": "mythic",
  "content": "不朽盾弓（Immortal Shieldbow）- 射手神话装备\n\n属性：+50攻击力，+20%攻击速度，+20%暴击几率，+7%生命偷取\n\n神话被动：每出一件传说装备，获得+8攻击力和+15生命值\n\n主动/被动效果：救主灵刃 - 受到将生命值降至30%以下的伤害时，获得护盾（基于额外攻击力）和额外生命偷取，持续8秒。（90秒冷却）\n\n适用英雄：\n- 亚索（核心装备，配合被动暴击翻倍）\n- 永恩（同上）\n- 薇恩（替代海妖的保命选择）\n- 烬、女警等需要保命的ADC\n\n出装时机：第一件或第二件\n\n搭配装备：无尽之刃（暴击伤害提升）、饮血剑（吸血叠加）\n\n注意事项：\n- 护盾可被重伤效果削减\n- 触发后90秒内无护盾，需谨慎在此期间开团\n- 对抗爆发型刺客（劫、男刀）时优先级最高",
  "keywords": [
    "不朽盾弓",
    "神话装备",
    "ADC",
    "护盾",
    "暴击",
    "吸血"
  ],
  "embedding_text": "不朽盾弓 神话装备 ADC 护盾 暴击 吸血 救主灵刃"
}
```

---

### item_riftmaker

```json
{
  "doc_id": "item_riftmaker",
  "doc_type": "item_reference",
  "item_name": "裂隙制造者",
  "item_category": "mythic",
  "content": "裂隙制造者（Riftmaker）- 法师/法坦神话装备\n\n属性：+80法术强度，+300生命值，+15技能急速，+8%全能吸血\n\n神话被动：每出一件传说装备，获得+2%全能吸血和+8法术强度\n\n被动效果：虚空腐蚀 - 对英雄造成伤害时，每秒造成额外魔法伤害（基于法强），持续3秒。在满层时，额外伤害转为真实伤害。\n\n适用英雄：\n- 莫德凯撒（核心装备，配合被动光环持续触发）\n- 格温（真实伤害契合机制）\n- 卡萨丁、瑞兹等持续输出法师\n- 铁男、炼金等法坦\n\n出装时机：第一件神话装\n\n搭配装备：\n- 瑞莱的冰晶节杖（减速黏人，持续触发腐蚀）\n- 中娅沙漏（保命+法强）\n- 恶魔之拥（双百分比伤害）\n\n注意事项：\n- 需要持续输出3秒才能触发真实伤害\n- 不适合爆发型法师（安妮、小鱼人）\n- 全能吸血对AOE技能有33%效能削减",
  "keywords": [
    "裂隙制造者",
    "神话装备",
    "法坦",
    "全能吸血",
    "真实伤害",
    "持续输出"
  ],
  "embedding_text": "裂隙制造者 神话装备 法坦 全能吸血 真实伤害 持续输出"
}
```

---

### rune_conqueror

```json
{
  "doc_id": "rune_conqueror",
  "doc_type": "rune_reference",
  "rune_name": "征服者",
  "rune_tree": "精密",
  "rune_type": "keystone",
  "content": "征服者（Conqueror）- 精密系基石符文\n\n机制：对敌方英雄造成伤害时获得自适应之力，持续6秒，最多叠加12层。满层后，对英雄造成伤害的15%转化为治疗效果。\n\n数值：每层提供1.2-3.6自适应之力（基于等级）。满层14.4-43.2自适应之力。\n\n适用场景：\n- 持续作战的战士和法坦（剑魔、铁男、诺手、鳄鱼）\n- 需要续航的近战英雄\n- 对抗坦克时提供持续输出和回血\n\n最佳搭配：\n- 传说：韧性（减少控制时间）\n- 传说：欢欣（提升攻速）\n- 坚毅不倒（低血量增伤）\n\n对比其他基石：\n- vs 致命节奏：征服者适合持续换血，致命节奏适合爆发输出\n- vs 强攻：征服者适合单挑，强攻适合配合队友集火\n- vs 不灭之握：征服者适合输出，不灭适合坦克换血\n\n触发英雄：莫德凯撒、德莱厄斯、亚托克斯、雷克顿、贾克斯",
  "keywords": [
    "征服者",
    "精密",
    "基石符文",
    "战士",
    "续航",
    "自适应之力"
  ],
  "embedding_text": "征服者 精密系 基石符文 战士 续航 自适应之力 治疗"
}
```

---

### rune_lethal_tempo

```json
{
  "doc_id": "rune_lethal_tempo",
  "doc_type": "rune_reference",
  "rune_name": "致命节奏",
  "rune_tree": "精密",
  "rune_type": "keystone",
  "content": "致命节奏（Lethal Tempo）- 精密系基石符文\n\n机制：对敌方英雄造成伤害后，获得攻击速度加成，持续6秒。通过攻击英雄可将效果延长至6秒，最多叠加6层。\n\n数值：每层提供5-15%攻击速度（基于等级），满层30-90%额外攻速。满层后攻击速度可突破2.5上限。\n\n适用场景：\n- 依赖攻速的ADC和战士（薇恩、亚索、永恩、金克丝）\n- 需要突破攻速上限的英雄\n- 持续输出型英雄\n\n最佳搭配：\n- 传说：欢欣（进一步提升攻速）\n- 砍倒（对抗高血量目标）\n- 坚毅不倒（低血量增伤）\n\n对比其他基石：\n- vs 强攻：致命节奏适合长时输出，强攻适合短时爆发\n- vs 征服者：致命节奏适合远程，征服者适合近战\n- vs Fleet Footwork：致命节奏纯输出，Fleet提供移速和续航\n\n触发英雄：亚索、永恩、薇恩、金克丝、厄斐琉斯、泽丽",
  "keywords": [
    "致命节奏",
    "精密",
    "基石符文",
    "攻速",
    "ADC",
    "突破上限"
  ],
  "embedding_text": "致命节奏 精密系 基石符文 攻速 ADC 突破上限 持续输出"
}
```

---

## 5. AI/RAG使用指南

### 5.1 检索策略

**基于关键词的精确检索**：
```python
def keyword_search(docs, query_keywords):
    results = []
    for doc in docs:
        score = sum(1 for kw in query_keywords if kw in doc["keywords"])
        if score > 0:
            results.append((doc, score))
    return sorted(results, key=lambda x: x[1], reverse=True)
```

**基于embedding的语义检索**：
```python
def semantic_search(docs, query, embedding_model):
    query_vec = embedding_model.encode(query)
    results = []
    for doc in docs:
        doc_vec = embedding_model.encode(doc["embedding_text"])
        similarity = cosine_similarity(query_vec, doc_vec)
        results.append((doc, similarity))
    return sorted(results, key=lambda x: x[1], reverse=True)
```

### 5.2 问答场景映射

| 用户问题类型 | 检索字段 | 文档类型过滤 |
|-------------|----------|-------------|
| "亚索怎么玩" | hero_name="亚索" | hero_profile |
| "亚索Q技能机制" | hero_name="亚索" + ability_key="Q" | ability_guide |
| "亚索中路出装" | hero_name="亚索" + role="Mid" | build_guide |
| "亚索怎么打玛尔扎哈" | hero_a="Yasuo" + hero_b="Malzahar" | matchup_analysis |
| "不朽盾弓适合谁" | item_name="不朽盾弓" | item_reference |
| "征服者符文效果" | rune_name="征服者" | rune_reference |
| "魔腾刷野路线" | hero_name="魔腾" + topic="jungle_pathing" | gameplay_guide |

### 5.3 向量化文本构建原则

`embedding_text` 字段的设计原则：
1. **包含核心实体**：英雄名、装备名、符文名必须出现
2. **包含属性标签**：位置、攻击类型、资源类型
3. **包含机制关键词**：暴击、击飞、真实伤害、压制等
4. **避免冗余**：不重复content中的完整句子
5. **中文优先**：面向中文用户的检索系统

示例对比：
- 差："亚索是一个很强的英雄，他的Q技能很厉害"
- 好："亚索 疾风剑豪 近战物理刺客 中路 暴击 击飞 风墙"

### 5.4 数据扩展规范

新增文档时必须包含：
1. 唯一的 `doc_id`（建议格式：`type_hero_topic`）
2. 准确的 `doc_type`（必须在document_types列表中）
3. 详细的 `content`（至少200字，包含机制、数值、技巧）
4. 5-10个 `keywords`（覆盖英雄、机制、装备、策略）
5. 精简的 `embedding_text`（20-30字，关键词密集）

---

*本文档为知识库标准格式，可直接导入向量数据库（如Pinecone、Milvus、Qdrant）或用于RAG系统构建。*
