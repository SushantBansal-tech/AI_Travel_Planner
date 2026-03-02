# ✈️ AI-Powered Travel Planning & Automated Booking System

An **end-to-end AI automation platform** that plans personalized travel itineraries, finds the **cheapest flights and hotels**, and **automatically books hotels** using real-world travel APIs.

This project showcases **AI-driven decision making**, **API orchestration**, and **production-grade automation** in the travel domain.

---

## 🚀 Features

- 🤖 **AI-Based Itinerary Planning**
  - Generates day-wise travel itineraries
  - Optimizes attraction order using geospatial logic

- ✈️ **Cheapest Flight Search**
  - Compares real-time flight prices
  - Returns best-value flight options

- 🏨 **Smart Hotel Discovery**
  - Finds hotels near itinerary locations
  - Filters by price, rating, and availability

- 🔁 **Automatic Retry & Fallback**
  - Skips non-bookable hotels
  - Retries until a valid bookable offer is found

- 🧾 **Automated Hotel Booking**
  - Books hotels using verified offer IDs
  - Handles guest details and payments end-to-end

---

## 🧠 System Architecture

```text
User Input
   ↓
AI Itinerary Generator
   ↓
Flight Search API
   ↓
Hotel List API (Geocode)
   ↓
Hotel Search API (Offers)
   ↓
Retry & Fallback Engine
   ↓
Hotel Booking API
   ↓
Booking Confirmation

