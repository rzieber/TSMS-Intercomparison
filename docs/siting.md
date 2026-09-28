# Site conditions and siting limitations

Known limitations of the observation sites that affect how results can be interpreted,
especially for 2-m winds. These are flaws of the study design, not of the 3D-PAWS hardware or
the analysis, and they should be stated wherever wind results are reported. Related:
[sensor-failures.md](sensor-failures.md), [method-differences.md](method-differences.md) (WD2),
[potential-fixes.md](potential-fixes.md) (PF-27).

Last updated 2026-09-28.

---

## Summary

| Site | Siting | Effect on 2-m wind | How to treat wind results |
|---|---|---|---|
| **Konya** | In a courtyard next to a brick wall, in the middle of the city | Severe. The 3D-PAWS anemometers and vanes sit in the wall's and buildings' wake, so 2-m winds are not representative of the free flow the 10-m reference sees | Treat 2-m wind comparisons as **not meaningful**. Report them only to document the siting effect |
| **Ankara** | A nearby hill strongly affects 2-m winds | Substantial, but less than Konya | Treat as **compromised**. Direction and speed differences are dominated by terrain, not sensor performance |
| **Adana** | No known siting problem for wind | Normal: agreement improves in steady winds, as expected | Use as the site for judging 3D-PAWS wind-sensor performance |

Source: PI / field-team knowledge of the sites (2026-09-28). Detailed site descriptions, photos,
and sensor heights relative to the obstructions are not yet in this repo. Adding them is
recommended, along with a formal siting class per variable from WMO-No. 8 Vol. I, Ch. 1,
Annex 1.D (Siting classifications for surface observing stations on land). WMO's Annex 1.G
measurement quality classification treats siting uncertainty separately from sensor quality,
so a formal siting class lets Konya/Ankara wind results be reported without blaming the sensors.

## Evidence in the data (hourly analysis, 2026-09-28)

Wind statistics split by regime, classified by the reference's 10-m speed: *variable*
< 3.0 m/s, *non-variable* ≥ 3.0 m/s.

- **Adana (control):** direction error *drops* in non-variable winds (MAE ≈ 10°, median bias
  −3° to −6°), which is what a well-exposed vane should do.
- **Ankara:** in non-variable winds the 3D-PAWS direction is rotated clockwise and the speed is
  much lower. At TSMS01 the reference flow is NNE–NE, while 3D-PAWS shows E–S for the same hours.
  Its median speed is 0.68 m/s vs. 2.23 m/s for the reference adjusted to 2 m, and the median
  direction offset is +30° to +66° depending on the averaging method.
  [Figure](figures/tsms01-nonvariable-windrose-vs-reference.png).
- **Konya:** the direction offset grows further in steady winds (TSMS04/05 median ≈ +100–110°).
  Only 3.3% of reference minutes are non-variable (≈ 200–330 h per station), so steady-wind
  statistics are also thin. **Caveat:** TSMS03, 04 and 05 wind data from 1 Dec 2024 (and
  Jan–Mar 2024) is also affected by the CHORDS column misalignment (SF-10), so Konya wind
  results must be regenerated after that's fixed before any siting conclusion is quantified.

A weaker wind combined with a rotated direction at the 2-m mast is the expected signature of
sheltering and deflection by obstacles. It matches the known site conditions.

## Implications

1. **Don't attribute Konya or Ankara 2-m wind differences to the 3D-PAWS sensors.** State the
   siting limitation alongside every wind table or figure.
2. **Hellmann height adjustment assumes an unobstructed profile.** At Konya and Ankara the
   10-m → 2-m adjustment isn't physically valid, so "adjusted reference" speeds there are only
   nominal.
3. **The TSMS report attributes Konya's weak wind agreement partly to "local flow conditions,
   instrument exposure, siting"** (Table 8 discussion). That's consistent with this. It's worth
   making the courtyard/wall and hill conditions explicit in feedback.
4. **Other variables:** a courtyard next to a brick wall can also affect temperature (radiated
   heat from the wall, reduced ventilation) and precipitation catch (wind shadow, splash). Not
   yet assessed. Worth checking Konya temperature bias by time of day and sun exposure.
