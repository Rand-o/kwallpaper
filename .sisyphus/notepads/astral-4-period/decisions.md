# Decisions - astral-4-period

## Architectural Decisions

### Timezone Handling
- Use `datetime.now(timezone)` with configured timezone
- Fixed bug where Astral times (timezone-aware) were compared with system time (naive)

### 4-Period Logic
```
if now < dawn: return "night"
elif dawn <= now < sunrise: return "sunrise"
elif sunrise <= now < sunset: return "day"
elif sunset <= now < dusk: return "sunset"
else: return "night"
```

### Boundary Conditions
- Merge periods if dawn≈sunrise or sunset≈dusk (< 5 minutes apart)
- Fallback to hour-based detection if any time is None (polar regions)

### Image Selection
- New `select_image_for_time()` function replaces interval cycling
- Sunrise: 3 images (before/at/after timing)
- Sunset: 4 images (before/during/going under/completed)
- Day/Night: Evenly spaced based on duration
