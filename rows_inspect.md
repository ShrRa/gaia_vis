## Visualization-specific type reasoning

The notebook (from Alex) recommends types from a **lossless / analysis** perspective — enough precision that no scientific information is degraded. The "Notes" column below refines those recommendations for a **sky visualization** context, where two additional constraints apply:

1. **Perceptual sufficiency**: only as much precision as a human observer can distinguish on screen.
2. **Rendering pipeline fit**: types that map cleanly to GPU colormaps


---

### 1. `int16×0.001` over `float16` for colormap-mapped quantities

This applies to: magnitudes (G, BP, RP), color indices (bp_rp, bp_g, g_rp), logg, and [M/H].

`float16` is an IEEE floating-point format with a 10-bit mantissa. Its key property is **non-uniform quantization**: values near zero are represented with very fine steps, while values far from zero have coarser steps. The ULP (unit in the last place — the smallest representable difference) grows with the magnitude of the value. For example, float16 ULP at bp_rp = 0.5 is ~0.00003, but at bp_rp = 10 it is ~0.001. This means two stars with bp_rp = 10.000 and bp_rp = 10.0005 are stored identically, while two stars at bp_rp = 0.001 and bp_rp = 0.0005 are stored with much finer distinction.

For visualization, this non-uniformity matters when you map a range of values to a colormap. A colormap is typically a lookup table of N colors, uniformly spaced across the data range. When the data values themselves are non-uniformly quantized, the mapping from data to colormap index introduces subtle inconsistencies — regions of the colormap that should represent equal physical intervals are populated by unequal numbers of float16 levels. In practice this can produce faint banding or uneven color gradients.

`int16×0.001` stores values as integers with a fixed 1 mmag (or 1 millidex) step. Every interval of the same physical size contains exactly the same number of representable values. This is **uniform quantization**, which maps to colormap indices without artifacts. The precision (1 mmag) far exceeds what the human eye can discriminate (~100 mmag for brightness, ~50–100 mmag for color), and the range (±32.767 in the scaled unit) comfortably covers all relevant fields.

A practical note: neither float16 nor int16×0.001 is native to GPU fragment shaders in the same way float32 is. Both require a conversion step at upload time or in the shader. Given that, int16×0.001 imposes no additional cost and buys clean colormap behavior.

---

### 2. `uint16` over `float16` for effective temperature

Temperature (teff_gspphot) is different from magnitudes and colors because it will almost certainly be used through a **precomputed blackbody colormap** rather than a linear scale. The workflow is: compute a lookup table of RGB colors for integer temperatures 2500–41500 K (one entry per Kelvin), then for each star look up its color by temperature index.

For this workflow, uint16 is the natural format: the stored value is literally the LUT index. Float16 would require a round-trip conversion (float16 → float32 → round to nearest integer → LUT index) that introduces small but unnecessary complications.

Beyond the LUT argument, there is a perceptual reason to prefer uint16 here. The human eye does not perceive temperature as a linear scale. The blackbody emission peak shifts from infrared into the visible range over roughly 3000–10000 K, producing dramatic color changes (deep red → orange → yellow → white). Above ~10000 K, the peak moves into the UV and the visible color changes become progressively subtler — a 40000 K star and a 30000 K star both appear blue-white and are visually nearly indistinguishable. Float16 has a ULP of ~32 K at 40000 K, which is coarser than uint16's 1 K, and the non-uniformity means its precision is worst exactly where the perceptual color change is slowest (hot stars). Uint16's uniform 1 K steps cover the full range cleanly and make no assumptions about where precision matters.

---

### 3. Float16 is actually preferred over float32 for `distance_gspphot`

The notebook recommends float32 for distance. For 3D sky visualization, float16 would be sufficient as well because the quantization error is always smaller than the photometric distance uncertainty — at every distance in the range.

Also float16's non-uniform precision becomes an **asset** when the quantity is a spatial coordinate. In 3D rendering, nearby objects require much more precise positioning than distant objects. A star 5 pc away is rendered at a specific point in the Galactic neighborhood; a star 30 kpc away is one dot in a diffuse background cloud. The position of the latter matters far less to the final image.
So when visualization is centered around Sun or Earth objects near them would be visualized with more precison than the further ones. If the user wants to zoom to some object far from our center these might need to be geathered with more precison (depends on the visualization requirements - could be obtained at that moment and does not need to be cached). GAIA archive data are centered around the Solar System Barycentre. 

Float16's precision profile matches this: at 1–10 pc it gives sub-0.01 pc precision; at 100 pc about 0.01 pc; at 10000 pc about 1 pc. All of these are sub-percent relative error, which is far finer than the photometric uncertainty on the distance estimate itself (~10–30%). At the far end (36000 pc), ULP ≈ 32 pc, giving ~0.1% relative error — still invisible in a rendered scene. Float32 is wasted precision at all distances, while float16 gives naturally distance-adaptive precision at half the memory footprint.

Note: this logic applies to `distance_gspphot` (max ~36 kpc, fits in float16). `r_med_photogeo` exceeds float16's maximum (79661 pc > 65504), so float32 remains required there. If storage is critical for that column, `log10(r_med_photogeo)` stored as float16 (range ~1.7–4.9, uniform ~0.003% relative precision) is a viable transform for a log-depth rendering pipeline.

---

### 4. Proper motion and animation

Currently not relevant, because we are focusing on visualization, but just in case if at some point it becomes relevant. 
For pm, pmra, pmdec, `float16` is recommended (the notebook suggests `float32`). The use case of particle animation: each star is moved across the sky by its proper motion vector at each animation frame.

In an animation context, the **direction** of the proper motion vector (the angle arctan(pmdec/pmra)) is as important as its magnitude — a star moving the wrong way is more visually wrong than a star moving at 99% of the correct speed. Float16 preserves direction particularly well because the overwhelming majority of stars have pm < 100 mas/yr, placing them squarely in the high-precision region of float16 (ULP < 0.006 at pm = 50). The rare high-pm stars (Barnard's star at ~10000 mas/yr) have ULP ≈ 8 mas/yr in float16 — coarse in absolute terms, but these objects are rendered as visibly fast-moving points and the exact speed difference is unimportant for the animation.

---

| # | column | min | max | nulls | Alex (lossless) | Notes: can be smaller for visualization |
|---|--------|-----|-----|-------|-----------------|-----------------------------------------|
| 1 | source_id | 4295806720 | 6917528997577384000 | 0 | uint64 | |
| 2 | ra | 3.4096239126626443e-7 | 359.999999939548 | 0 | float32 | **Important:** must be high, otherwise jittering could appear when zooming  |
| 3 | ra_error | 0.0035371692 | 99.997635 | 0 | float32 | **float16**: 0.004–100 mas → ~1600 levels; ULP ≈ 0.06 at max |
| 4 | dec | -89.99287859590359 | 89.99005196682685 | 0 | float32 | **Important:** must be high, otherwise jittering could appear when zooming |
| 5 | dec_error | 0.0042951643 | 99.97974 | 0 | float32 | **float16**: same as ra_error |
| 6 | parallax | -187.02939637423492 | 768.0665391873573 | 343964953 | float32 |  |
| 7 | parallax_error | 0.0071899574 | 5.802274 | 343964953 | float32 | **float16**: 0.007–5.8 mas → ~1450 levels; ULP ≈ 0.004 at max |
| 8 | parallax_over_error | -161.38797 | 15400.477 | 343964953 | float32 or float16 | **float16**: Alex also suggests it; quality indicator, 3 sig digits sufficient |
| 9 | pm | 0.00019370936 | 10393.349 | 343964953 | float32 | **float16**: 0–10393 mas/yr → ~1900 levels; ULP ≈ 8 at max. |
| 10 | pmra | -4406.469178827325 | 6765.995136250774 | 343964953 | float32 | **float16**: same as pm | 
| 11 | pmra_error | 0.0039596637 | 3.447368 | 343964953 | float32 | **float16**: 0–3.4 mas/yr → ~850 levels; ULP ≈ 0.002 at max |
| 12 | pmdec | -5817.8001940492695 | 10362.394206546573 | 343964953 | float32 | **float16**: same as pm |
| 13 | pmdec_error | 0.0052927267 | 3.4449604 | 343964953 | float32 | **float16**: same as pmra_error |
| 14 | phot_g_mean_flux | 12.370194398444749 | 3822116782.6336956 | 5455339 | float32 |  |
| 15 | phot_g_mean_flux_error | 0.27475065 | 61207728 | 5455339 | float32 |  |
| 16 | phot_g_mean_flux_over_error | 1.0823672 | 22926.803 | 5455339 | float32 or float16 | **float16**: Alex also suggests it; max 22927 < 65504; ULP ≈ 2 at max |
| 17 | phot_g_mean_mag | 1.731607 | 22.956425 | 5455339 | float32 or int16×0.001 | **int16×0.001 preferred over float16**: uniform 1 mmag steps map cleanly to colormap LUTs; |
| 18 | phot_bp_mean_flux | 1.0050400371436263 | 1500432409.3837109 | 269676299 | float32 |  |
| 19 | phot_bp_mean_flux_error | 0 | 71123240 | 269676299 | float32 |  |
| 20 | phot_bp_mean_flux_over_error | 0.053431902 | 94195456 | 269676302 | float32 or float16 |  |
| 21 | phot_bp_mean_mag | 2.3980012 | 25.333084 | 269676299 | float32 or int16×0.001 | **int16×0.001 preferred**: same reasoning as phot_g_mean_mag |
| 22 | phot_rp_mean_flux | 1.0489614290056928 | 1591127209.4126902 | 256711832 | float32 |  |
| 23 | phot_rp_mean_flux_error | 0 | 89607720 | 256711832 | float32 |  |
| 24 | phot_rp_mean_flux_over_error | 0.054578356 | 81374416 | 256711835 | float32 or float16 | float32 required: max 8.1×10⁷ overflows float16 |
| 25 | phot_rp_mean_mag | 1.7436333 | 24.695997 | 256711832 | float32 or int16×0.001 | **int16×0.001 preferred**: same reasoning as phot_g_mean_mag |
| 26 | bp_rp | -7.3475304 | 10.193149 | 270939282 | float32 or int16×0.001 | **int16×0.001 preferred over float16**: color is the primary visual encoding for star type — uniform 1 mmag steps map cleanly to colormap indices.  |
| 27 | bp_g | -8.431045 | 7.015131 | 269681608 | float32 or int16×0.001 | **int16×0.001 preferred**: same reasoning as bp_rp |
| 28 | g_rp | -4.8746176 | 11.520412 | 260559960 | float32 or int16×0.001 | **int16×0.001 preferred**: same reasoning as bp_rp |
| 29 | radial_velocity | -906.6071 | 914.7007 | 1777897588 | float32 | **float16**: ±914 km/s; ULP ≈ 0.06 km/s at max, Gaia RVS precision is 0.1–1 km/s |
| 30 | radial_velocity_error | 0.11300004 | 39.99959 | 1777897588 | float32 | **float16**: 0.11–40 km/s; ULP ≈ 0.03 at max |
| 31 | phot_variable_flag | OBJECT - char | | | uint8 (or 4-flag bitfield) |  |
| 32 | l | 1.0606335061246415e-7 | 359.9999999850258 | 0 | float32 |  |
| 33 | b | -89.99366530605397 | 89.98796453163729 | 0 | float32 |  |
| 34 | ecl_lon | 5.21887866629631e-7 | 359.99999810830957 | 0 | float32 |  |
| 35 | ecl_lat | -89.99954651413846 | 89.99008000608518 | 0 | float32 |  |
| 36 | in_qso_candidates | False | True | | uint8 (or 4-flag bitfield) | bool (1 byte); Alex suggests packing all 4 flag columns into a single uint8 bitfield |
| 37 | in_galaxy_candidates | False | True | | uint8 (or 4-flag bitfield) | bool; same note as in_qso_candidates |
| 38 | non_single_star | 0 | 7 | 0 | uint8 (or 4-flag bitfield) | **uint8**; Important! Alex's suggestion of 4 bitfield is not valid in this case because values of this field are accutaly between 0 and 7 and all values occure |
| 39 | teff_gspphot | 2501.1814 | 41504.02 | 1340950508 | float32 or uint16 | **uint16 preferred over float16**: stores exact integer K values, making LUT-based temperature-to-color (blackbody) mapping trivial  |
| 40 | teff_gspphot_lower | 2500.3027 | 41460.203 | 1340950508 | float32 or uint16 | **uint16 preferred**: same reasoning as teff_gspphot |
| 41 | teff_gspphot_upper | 2503.5662 | 41532.008 | 1340950508 | float32 or uint16 | **uint16 preferred**: same reasoning as teff_gspphot |
| 42 | logg_gspphot | -0.5 | 5.4957 | 1340950508 | float32 or int16×0.001 | **int16×0.001 preferred over float16** |
| 43 | logg_gspphot_lower | -0.5 | 5.487 | 1340950508 | float32 or int16×0.001 | **int16×0.001 preferred over float16** |
| 44 | logg_gspphot_upper | -0.4999 | 5.4992 | 1340950508 | float32 or int16×0.001 | **int16×0.001 preferred over float16** |
| 45 | mh_gspphot | -4.1503 | 0.8 | 1340950508 | float32 or int16×0.001 | **int16×0.001 preferred over float16** |
| 46 | mh_gspphot_lower | -4.1505 | 0.7999 | 1340950508 | float32 or int16×0.001 | **int16×0.001 preferred over float16** |
| 47 | mh_gspphot_upper | -4.1498 | 0.8001 | 1340950508 | float32 or int16×0.001 | **int16×0.001 preferred over float16** |
| 48 | distance_gspphot | 1.3011 | 36165.09 | 1340950508 | float32 | float16 |
| 49 | distance_gspphot_lower | 1.3006 | 35664.418 | 1340950508 | float32 | float16 |
| 50 | distance_gspphot_upper | 1.3013 | 36337.793 | 1340950508 | float32 | float16 |
| 51 | r_med_photogeo | 1.3019346 | 79661.01 | 121123187 | float32 |  |
