/*
 Navicat Premium Data Transfer

 Source Server         : 火币网格
 Source Server Type    : SQLite
 Source Server Version : 3030001
 Source Schema         : main

 Target Server Type    : SQLite
 Target Server Version : 3030001
 File Encoding         : 65001

 Date: 07/07/2021 18:51:59
*/

PRAGMA foreign_keys = false;

-- ----------------------------
-- Table structure for orders
-- ----------------------------
DROP TABLE IF EXISTS "orders";
CREATE TABLE "orders" (
  "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  "order_id" text,
  "side" TEXT,
  "price" real,
  "amount" real,
  "create_time" DATE
);

PRAGMA foreign_keys = true;
