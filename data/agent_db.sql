/*
 Navicat Premium Data Transfer

 Source Server         : 本地数据库
 Source Server Type    : MySQL
 Source Server Version : 80024
 Source Host           : localhost:3306
 Source Schema         : agent_db

 Target Server Type    : MySQL
 Target Server Version : 80024
 File Encoding         : 65001

 Date: 10/06/2026
 Note: 向量存储已迁移至 Qdrant，此文件仅保留会话和消息相关表
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for sessions（更新为匹配 Session 模型）
-- ----------------------------
DROP TABLE IF EXISTS `sessions`;
CREATE TABLE `sessions`  (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `session_id` varchar(64) NOT NULL COMMENT '会话唯一ID',
  `user_id` int NULL DEFAULT NULL COMMENT '用户ID',
  `agent_type` varchar(50) NOT NULL COMMENT 'Agent类型',
  `status` varchar(20) DEFAULT 'active' COMMENT '状态',
  `title` varchar(200) NULL DEFAULT NULL COMMENT '会话标题',
  `model_name` varchar(100) NOT NULL COMMENT '模型名称',
  `system_prompt` text NULL COMMENT '系统提示词',
  `config` json NULL COMMENT '配置',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `ended_at` datetime NULL DEFAULT NULL COMMENT '结束时间',
  `message_count` int DEFAULT 0 COMMENT '消息数量',
  `token_count` int DEFAULT 0 COMMENT 'Token数量',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_session_id`(`session_id` ASC) USING BTREE,
  INDEX `idx_user_id`(`user_id` ASC) USING BTREE,
  INDEX `idx_status`(`status` ASC) USING BTREE,
  INDEX `idx_created_at`(`created_at` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '会话表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of sessions
-- ----------------------------
INSERT INTO `sessions` VALUES (1, 'default-session-001', NULL, 'chat', 'active', '默认会话', 'qwen3-max', NULL, NULL, '2026-06-09 02:52:20', '2026-06-09 08:21:56', NULL, 0, 0);

-- ----------------------------
-- Table structure for messages（更新为匹配 Message 模型）
-- ----------------------------
DROP TABLE IF EXISTS `messages`;
CREATE TABLE `messages`  (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '消息ID',
  `session_id` varchar(64) NOT NULL COMMENT '会话ID（关联sessions.session_id）',
  `role` varchar(20) NOT NULL COMMENT '角色',
  `content` text NOT NULL COMMENT '消息内容',
  `token_count` int DEFAULT 0 COMMENT 'Token数量',
  `model_name` varchar(100) NULL DEFAULT NULL COMMENT '模型名称',
  `tool_calls` json NULL COMMENT '工具调用记录',
  `tool_results` json NULL COMMENT '工具返回结果',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_session_id`(`session_id` ASC) USING BTREE,
  INDEX `idx_created_at`(`created_at` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '消息表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of messages (示例数据)
-- ----------------------------
INSERT INTO `messages` VALUES (1, 'default-session-001', 'user', '你好', 0, NULL, NULL, NULL, '2026-06-09 02:52:20');
INSERT INTO `messages` VALUES (2, 'default-session-001', 'assistant', '您好！有什么可以帮您的吗？', 0, 'qwen3-max', NULL, NULL, '2026-06-09 02:52:25');

-- ----------------------------
-- Table structure for news (可选)
-- ----------------------------
DROP TABLE IF EXISTS `news`;
CREATE TABLE `news`  (
  `id` int UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '新闻ID',
  `title` varchar(255) NOT NULL COMMENT '新闻标题',
  `description` varchar(500) NULL DEFAULT NULL COMMENT '新闻简介',
  `content` text NOT NULL COMMENT '新闻内容',
  `image` varchar(255) NULL DEFAULT NULL COMMENT '封面图片URL',
  `author` varchar(50) NULL DEFAULT NULL COMMENT '作者',
  `category_id` int UNSIGNED NOT NULL COMMENT '分类ID',
  `views` int UNSIGNED NOT NULL DEFAULT 0 COMMENT '浏览量',
  `publish_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发布时间',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '新闻表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for users (可选)
-- ----------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users`  (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `username` varchar(50) NOT NULL COMMENT '用户名',
  `email` varchar(100) NULL DEFAULT NULL COMMENT '邮箱',
  `password_hash` varchar(255) NULL DEFAULT NULL COMMENT '密码哈希',
  `status` varchar(20) DEFAULT 'active' COMMENT '状态',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_username`(`username` ASC) USING BTREE,
  INDEX `idx_email`(`email` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '用户表' ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;