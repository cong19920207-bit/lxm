# 林小梦 - 设计系统规范

## 🎨 设计风格

### 核心风格：漫画/动漫风格
- **粗黑边框**：所有元素都有明显的黑色描边
- **扁平阴影**：使用 `shadow-[Xpx_Ypx_0_0_rgba(0,0,0,0.3)]` 实现立体效果
- **圆润造型**：大量使用圆角（rounded-2xl, rounded-3xl, rounded-full）
- **鲜艳配色**：明亮的渐变色彩
- **动画丰富**：所有交互都带有弹性动画

---

## 🎨 颜色系统

### 主色调
```css
/* 背景渐变 */
background: linear-gradient(to bottom right, #fce7f3, #e9d5ff, #dbeafe);
/* from-pink-100 via-purple-100 to-blue-100 */

/* 主要文字 */
text-gray-800: #1f2937
text-gray-700: #374151
text-gray-600: #4b5563

/* 次要文字 */
text-gray-500: #6b7280
text-gray-400: #9ca3af
```

### 品牌色
```css
/* 粉色系 */
pink-400: #f472b6
pink-500: #ec4899
pink-600: #db2777

/* 紫色系 */
purple-400: #c084fc
purple-500: #a855f7
purple-600: #9333ea

/* 蓝色系 */
blue-400: #60a5fa
blue-500: #3b82f6

/* 橙色系 */
orange-400: #fb923c
orange-500: #f97316

/* 黄色系 */
yellow-400: #facc15
yellow-500: #eab308
```

### 功能色
```css
/* 成功/在线 */
green-400: #4ade80
green-500: #22c55e

/* 警告/未读 */
red-400: #f87171
red-500: #ef4444

/* 禁用 */
gray-200: #e5e7eb
gray-300: #d1d5db
```

---

## 🎯 边框系统

### 边框粗细
```css
border-3: 3px solid black
border-4: 4px solid black
border-5: 5px solid black
border-6: 6px solid black
```

### 常用组合
- **主要按钮**：`border-5 border-black`
- **卡片容器**：`border-5 border-black` 或 `border-4 border-black`
- **小图标**：`border-3 border-black`
- **输入框**：`border-4 border-black`

---

## 🌟 阴影系统

### 扁平阴影（漫画风格）
```css
/* 小元素 */
shadow-[2px_2px_0_0_rgba(0,0,0,0.2)]
shadow-[3px_3px_0_0_rgba(0,0,0,0.3)]

/* 中等元素 */
shadow-[4px_4px_0_0_rgba(0,0,0,0.3)]
shadow-[5px_5px_0_0_rgba(0,0,0,0.3)]

/* 大元素/卡片 */
shadow-[6px_6px_0_0_rgba(0,0,0,0.3)]
shadow-[8px_8px_0_0_rgba(0,0,0,0.3)]

/* 对话框/重要元素 */
shadow-[12px_12px_0_0_rgba(0,0,0,0.4)]

/* Hover 效果 */
hover:shadow-[6px_6px_0_0_rgba(0,0,0,0.3)]
hover:shadow-[10px_10px_0_0_rgba(0,0,0,0.3)]
```

---

## 📐 圆角系统

```css
rounded-xl: 12px      /* 小元素 */
rounded-2xl: 16px     /* 按钮、输入框 */
rounded-3xl: 24px     /* 卡片 */
rounded-full: 9999px  /* 圆形按钮、头像、徽章 */
```

---

## 🔘 按钮组件

### 主要按钮（Primary Button）
```tsx
className="h-16 bg-gradient-to-r from-blue-500 to-purple-500 
  rounded-full border-5 border-black 
  shadow-[8px_8px_0_0_rgba(0,0,0,0.3)] 
  hover:shadow-[10px_10px_0_0_rgba(0,0,0,0.3)]
  font-black text-white text-2xl"
```

### 次要按钮（Secondary Button）
```tsx
className="h-14 bg-white rounded-2xl border-4 border-black 
  shadow-[4px_4px_0_0_rgba(0,0,0,0.3)] 
  hover:shadow-[6px_6px_0_0_rgba(0,0,0,0.3)]
  font-bold text-black"
```

### 圆形图标按钮
```tsx
className="w-12 h-12 rounded-full bg-purple-400 
  border-4 border-black 
  shadow-[3px_3px_0_0_rgba(0,0,0,0.3)]
  flex items-center justify-center"
```

### 危险按钮（Danger Button）
```tsx
className="h-14 bg-gradient-to-r from-red-400 to-red-500 
  rounded-2xl border-4 border-black 
  shadow-[4px_4px_0_0_rgba(0,0,0,0.3)]
  font-black text-white"
```

### H5 首页（`index.html`，与 `docs/contract.md` 对齐）

- **Hero**：**`.home-hero`** 使用 **`/static/images/Index/index.png`** 铺满顶区；左下 **林小梦** 白字 + 星标 + **`.home-status-bubble`**（轻圆角白卡，无漫画三角尾巴）；**`#linxiaomeng-avatar`** 保留 DOM 仅 **`display:none`**。
- **顶栏**：叠在 Hero 上；左 **用户名首字** 半透明圆钮，右 **设置** 入口保留。
- **装饰**：黄/粉浮动球在 **`.home-hero .h5-home-decor`** 内，**`h5-wiggle` / `h5-float-y`**；减少动态效果时关闭。
- **未读角标**：`#unread-badge` 叠在「进入聊天」主按钮角上；仅 **`GET /api/agent/unread-count`** 的 **`count > 0`** 时展示，并加 **`.unread-badge--active`** 做轻量呼吸缩放。
- **状态语文**：**`#status-text`** 在 **`GET /api/relationship/status`** 成功后赋值（优先 **`data.status_text`**，否则默认「和你在一起的每一天都很开心」）。
- **关系区**：**`.home-rel-card`** 横卡（心形图标 + 等级文案 + 进度条 + 分数）；填充 **蓝→粉** 渐变，**`width` 0.8s 过渡**。
- **功能入口**：**`.home-feature-grid`** 三卡（标题 + 副标题 + chevron），跳转记忆/日记/关系；底部 **渐变胶囊**「进入聊天」+ 聊天气泡 SVG。

---

## 📦 卡片组件

### 标准卡片
```tsx
className="bg-white rounded-3xl border-5 border-black 
  shadow-[6px_6px_0_0_rgba(0,0,0,0.3)] p-5"
```

### 渐变卡片
```tsx
className="bg-gradient-to-br from-yellow-50 to-orange-50 
  rounded-3xl border-5 border-black 
  shadow-[8px_8px_0_0_rgba(0,0,0,0.3)] p-6"
```

### 小卡片
```tsx
className="bg-gradient-to-br from-gray-50 to-gray-100 
  rounded-2xl border-3 border-black 
  shadow-[3px_3px_0_0_rgba(0,0,0,0.3)] p-3"
```

---

## 📝 输入框组件

### 标准输入框
```tsx
className="w-full h-14 px-4 rounded-2xl 
  border-4 border-black 
  shadow-[4px_4px_0_0_rgba(0,0,0,0.3)] 
  focus:shadow-[6px_6px_0_0_rgba(0,0,0,0.3)]
  outline-none font-bold"
```

### 多行文本框
```tsx
className="w-full h-24 p-4 rounded-2xl 
  border-4 border-black 
  shadow-[4px_4px_0_0_rgba(0,0,0,0.3)]
  outline-none font-medium resize-none"
```

---

## 🔄 开关组件

### Toggle Switch
```tsx
/* 容器 */
className="relative w-14 h-8 rounded-full 
  border-4 border-black 
  shadow-[3px_3px_0_0_rgba(0,0,0,0.3)]
  bg-green-400 (开启) / bg-gray-300 (关闭)"

/* 滑块 */
className="absolute top-0.5 left-0.5 w-5 h-5 
  bg-white rounded-full 
  border-3 border-black 
  shadow-[2px_2px_0_0_rgba(0,0,0,0.2)]"
```

---

## 🎭 徽章组件

### 未读消息徽章
```tsx
className="min-w-[32px] h-8 px-2 
  bg-gradient-to-r from-red-400 to-red-500 
  rounded-full border-4 border-black 
  shadow-[4px_4px_0_0_rgba(0,0,0,0.3)]
  font-black text-white text-sm"
```

### 状态标签
```tsx
className="px-4 py-2 
  bg-green-100 border-3 border-green-600 
  rounded-full shadow-[2px_2px_0_0_rgba(0,0,0,0.2)]
  font-black text-green-700 text-sm"
```

---

## 🎬 动画效果

### 按钮动画
```tsx
whileHover={{ scale: 1.05, y: -3 }}
whileTap={{ scale: 0.95 }}
```

### 卡片动画
```tsx
whileHover={{ scale: 1.02, x: 3 }}
```

### 入场动画
```tsx
initial={{ opacity: 0, y: 20 }}
animate={{ opacity: 1, y: 0 }}
transition={{ delay: 0.1 }}
```

### 弹簧动画
```tsx
transition={{ type: "spring", stiffness: 500, damping: 15 }}
```

### 呼吸动画（未读消息）
```tsx
animate={{ scale: [1, 1.2, 1] }}
transition={{ duration: 2, repeat: Infinity }}
```

### 旋转动画（装饰元素）
```tsx
animate={{ rotate: [0, 360] }}
transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
```

### 漂浮动画
```tsx
animate={{ y: [0, -10, 0] }}
transition={{ duration: 3, repeat: Infinity }}
```

---

## 📱 页面布局

### 标准页面结构
```tsx
<div className="size-full bg-gradient-to-br from-pink-100 via-purple-100 to-blue-100 
  overflow-hidden relative flex flex-col">
  
  {/* 装饰元素 */}
  <motion.div className="absolute ...">
    <Sparkles />
  </motion.div>

  {/* 顶部导航栏 */}
  <motion.div className="relative z-10 bg-white border-b-6 border-black 
    shadow-[0_6px_0_0_rgba(0,0,0,0.3)] px-4 py-3">
    {/* 导航内容 */}
  </motion.div>

  {/* 内容区域 */}
  <div className="flex-1 overflow-y-auto p-4 space-y-4">
    {/* 页面内容 */}
  </div>
</div>
```

### 导航栏结构
```tsx
<div className="flex items-center justify-between">
  {/* 返回按钮 */}
  <motion.button className="w-12 h-12 rounded-full ...">
    <ArrowLeft />
  </motion.button>

  {/* 标题 */}
  <h2 className="text-xl font-black text-gray-800">页面标题</h2>

  {/* 右侧按钮/占位 */}
  <div className="w-12" />
</div>
```

---

## 🎨 渐变组合

### 按钮渐变
```css
from-blue-500 to-purple-500      /* 主按钮 */
from-pink-400 to-purple-400      /* 聊天气泡 */
from-pink-400 to-orange-400      /* 添加按钮 */
from-red-400 to-red-500          /* 危险/未读 */
from-yellow-400 to-orange-400    /* 日签按钮 */
```

### 背景渐变
```css
from-pink-100 via-purple-100 to-blue-100        /* 页面背景 */
from-gray-50 to-gray-100                        /* 卡片背景 */
from-yellow-50 to-orange-50                     /* 强调卡片 */
from-blue-300 to-purple-300                     /* 头像 */
from-yellow-200 to-yellow-300                   /* 关系状态头像 */
```

---

## 📏 间距系统

```css
/* 内边距 */
p-3: 12px    /* 小元素 */
p-4: 16px    /* 常规 */
p-5: 20px    /* 卡片 */
p-6: 24px    /* 大卡片 */

/* 间隔 */
gap-2: 8px   /* 紧凑 */
gap-3: 12px  /* 常规 */
gap-4: 16px  /* 宽松 */

/* 外边距 */
space-y-3: 12px  /* 垂直间距 */
space-y-4: 16px  /* 垂直间距 */
```

---

## 🖋 字体系统

### 字号
```css
text-xs: 12px      /* 辅助文字 */
text-sm: 14px      /* 次要文字 */
text-base: 16px    /* 正文 */
text-lg: 18px      /* 小标题 */
text-xl: 20px      /* 标题 */
text-2xl: 24px     /* 大标题 */
text-3xl: 30px     /* 超大标题 */
text-4xl: 36px     /* 数字 */
text-5xl: 48px     /* 主角名字 */
```

### 字重
```css
font-medium: 500   /* 输入框、正文 */
font-bold: 700     /* 强调文字 */
font-black: 900    /* 标题、按钮 */
```

---

## 🎯 特殊效果

### 文字描边（主角名字）
```tsx
style={{
  WebkitTextStroke: '3px black',
  paintOrder: 'stroke fill'
}}
className="text-transparent bg-clip-text bg-gradient-to-r from-pink-600 to-purple-600"
```

### 对话框三角
```tsx
{/* 黑色边框三角 */}
<div className="absolute -bottom-3 left-1/2 -translate-x-1/2 
  w-0 h-0 border-l-[15px] border-l-transparent 
  border-r-[15px] border-r-transparent 
  border-t-[15px] border-t-black" />

{/* 白色填充三角 */}
<div className="absolute -bottom-2 left-1/2 -translate-x-1/2 
  w-0 h-0 border-l-[12px] border-l-transparent 
  border-r-[12px] border-r-transparent 
  border-t-[12px] border-t-white" />
```

### 进度条动画
```tsx
<motion.div
  initial={{ width: 0 }}
  animate={{ width: `${percent}%` }}
  transition={{ duration: 1.5, ease: "easeOut" }}
  className="h-full bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400"
/>
```

---

## 🎪 装饰元素

### 漂浮星星
```tsx
<motion.div
  className="absolute top-20 right-16 text-yellow-400"
  animate={{ rotate: [0, 20, 0], scale: [1, 1.2, 1] }}
  transition={{ duration: 2, repeat: Infinity }}
>
  <Sparkles size={32} fill="currentColor" />
</motion.div>
```

### 跳动爱心
```tsx
<motion.div
  className="absolute top-20 left-10 text-pink-400"
  animate={{ rotate: [0, -20, 0], scale: [1, 1.3, 1] }}
  transition={{ duration: 2.5, repeat: Infinity }}
>
  <Heart size={28} fill="currentColor" />
</motion.div>
```

---

## 📋 页面清单

### 已完成页面
1. ✅ 登录页面 (`/`)
2. ✅ 注册页面 (`/register`)
3. ✅ 忘记密码 (`/forgot-password`)
4. ✅ 主页 (`/home`)
5. ✅ 聊天页面 (`/chat`)
6. ✅ 日记页面 (`/diary`)
7. ✅ 我们的关系 (`/relationship`)
8. ✅ 我的记忆 (`/memory`)
9. ✅ 设置页面 (`/settings`)

### 核心功能
- ✅ 未读消息徽章
- ✅ 开关切换
- ✅ 底部弹窗（添加记忆）
- ✅ 中心对话框（退出确认）
- ✅ 展开/收起内容
- ✅ 进度条动画
- ✅ 时间轴

---

## 🎨 设计原则

1. **一致性**：所有元素使用统一的粗黑边框和扁平阴影
2. **可预测性**：相似的交互使用相似的动画效果
3. **视觉层次**：通过边框粗细、阴影大小区分重要性
4. **动态感**：适度的动画让界面生动但不过度
5. **易读性**：使用足够的字重和对比度
6. **趣味性**：漫画风格带来愉悦的用户体验

---

## 📱 响应式设计

### 断点
```css
/* 移动端优先 */
默认: < 768px
md: >= 768px (平板)
lg: >= 1024px (桌面)
```

### 适配策略
- 移动端：单列布局
- 平板/桌面：可选多列布局
- 字体大小：使用响应式类如 `text-2xl md:text-3xl`
- 间距：使用响应式间距如 `p-4 md:p-6`

---

## 🔧 技术栈

- **框架**：React 18 + TypeScript
- **路由**：React Router v7
- **样式**：Tailwind CSS v4
- **动画**：Motion (Framer Motion)
- **图标**：Lucide React

---

**版本**：v1.0  
**最后更新**：2024年  
**维护者**：林小梦开发团队
