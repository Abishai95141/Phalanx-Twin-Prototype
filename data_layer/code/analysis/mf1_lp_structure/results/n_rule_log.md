# n-rule log (PREREGISTRATION.md section 7)

Target: bootstrap 95 % CI half-width <= 0.05 for the medians of CF_N1, CF_N2 and s_dyn (engine 1, ALL, N1-N2). Prefixes of results/flight_order.json.

- n = 20: CF_N1 median 0.690 [0.667, 0.720] h 0.027 sd 0.133; CF_N2 median 0.696 [0.669, 0.728] h 0.029 sd 0.128; s_dyn median 0.920 [0.880, 0.928] h 0.024 sd 0.131; class counts {'AT': 19, 'MAN': 10, 'CLB': 20, 'CRZ': 20, 'DES': 20, 'MAN_FLT': 1, 'AT_FLT': 19, 'FLT': 20, 'MAN_FLT_K1': 15}

**n_final = 20** (all half-widths <= 0.05: True)

- split coverage at n = 20: {'AT': 19, 'MAN': 10, 'CLB': 20, 'CRZ': 20, 'DES': 20, 'MAN_FLT': 1, 'AT_FLT': 19, 'FLT': 20, 'MAN_FLT_K1': 15}; short: {'MAN': 10}
- split coverage at n = 30: {'AT': 29, 'MAN': 18, 'CLB': 29, 'CRZ': 30, 'DES': 30, 'MAN_FLT': 1, 'AT_FLT': 29, 'FLT': 30, 'MAN_FLT_K1': 23}; short: none

**n_split = 30**

