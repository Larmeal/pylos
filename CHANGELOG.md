## v0.1.1 (2026-11-11)

### Fix

- **results**: read the version from the pylos-gx distribution ([`848584f`](https://github.com/Larmeal/pylos/commit/848584ffc0a8d00799c16299a642fc47f2634108))
- **build**: publish under the pylos-gx distribution name ([`ec0f278`](https://github.com/Larmeal/pylos/commit/ec0f2788fd12a304ed16b958b8b399ea4e3dd919))

## v0.1.0 (2026-11-11)

### Feat

- **storages**: list source objects in natural order ([`8092021`](https://github.com/Larmeal/pylos/commit/809202165f1ca0abc5762f5a5fedf62d95fd90f2))
- **gx**: name unnamed expectations after their contract and type ([`21c4709`](https://github.com/Larmeal/pylos/commit/21c47091499db42892cdff09189e74f7ec0249a3))
- handle the local test case and change engine to builder pattern ([`edbbe0d`](https://github.com/Larmeal/pylos/commit/edbbe0df4d6d728b7595c740e17a8b24d1b72909))
- add mode to on failure ([`5518ea9`](https://github.com/Larmeal/pylos/commit/5518ea92df1782c70e815712dd80278a65459f9f))
- add cosmos exceptions ([`11509f9`](https://github.com/Larmeal/pylos/commit/11509f9d41cf80151345b5e26a11cafee54c200a))
- add test case for dict_deep_merge ([`fea426a`](https://github.com/Larmeal/pylos/commit/fea426a16d802e7e6b039e2351825107f4a19f98))
- add test case for end to end local ([`bc32b14`](https://github.com/Larmeal/pylos/commit/bc32b14e658a1c998eb5cdd2e0b5136e0d8a0191))
- add dict merge key and test case ([`0e54d71`](https://github.com/Larmeal/pylos/commit/0e54d7161d7a948875a24a8e3874a11581e7fb4f))
- initial test cases ([`879df9f`](https://github.com/Larmeal/pylos/commit/879df9fd300dabad32783870a763b21a75412b54))
- add planner and modify engine parameter ([`e106b0d`](https://github.com/Larmeal/pylos/commit/e106b0dd7ee16e26e2f817d0bbd8d10571f33351))
- add policy ([`2ec6189`](https://github.com/Larmeal/pylos/commit/2ec618982e3360451b6ed86194fe196772a93cac))
- initial unittest with pytest ([`06828e3`](https://github.com/Larmeal/pylos/commit/06828e3e485617cd2582647dfdbd6cab3f94170d))
- add translate method to convert gx result to cosmos result ([`fd00f6c`](https://github.com/Larmeal/pylos/commit/fd00f6cd8a6a0b515c60b6aee2c946b6c03a376f))
- add sinks modules ([`1182792`](https://github.com/Larmeal/pylos/commit/1182792b262af3c627b4eeeff48c5cf863eb1e1b))
- add result model ([`0d95089`](https://github.com/Larmeal/pylos/commit/0d9508929623d4912d11fb96195c6539bbc64d43))
- add cosmos exceptions ([`fa400c7`](https://github.com/Larmeal/pylos/commit/fa400c7c3e414f2c24a3d41908c86481496f4e86))
- split the backend from source and action ([`c47a055`](https://github.com/Larmeal/pylos/commit/c47a0553137dac9cd22b8d04f8fc6ca1951c7de9))
- add committizen to repo ([`243e1ac`](https://github.com/Larmeal/pylos/commit/243e1ac7d77d2664018352ed28084f8a87546812))
- add localstorage ([`28d8e9d`](https://github.com/Larmeal/pylos/commit/28d8e9d155702b8f8c7875ee87ab5c67b795201a))
- add fsspec, gcsfs to gcp group ([`83f9574`](https://github.com/Larmeal/pylos/commit/83f9574093c32b65f029614390d76977bd08b5f8))
- add yaml loader ([`8688f89`](https://github.com/Larmeal/pylos/commit/8688f89834dbd2b9a97ff263035cb557263bf8a7))
- add loader configuration ([`b91d5bf`](https://github.com/Larmeal/pylos/commit/b91d5bf2e2513179461b69ea71f86bef943f7273))
- add gcp group and downgrade pandas to 2.2.3 ([`743a3d5`](https://github.com/Larmeal/pylos/commit/743a3d585585505e88590e9f1e6b37045e7f25a4))
- add destination for local type ([`e4910ca`](https://github.com/Larmeal/pylos/commit/e4910caaaad7d29b86e77038303a61ddf54390a7))
- add first draft of source ([`9174095`](https://github.com/Larmeal/pylos/commit/9174095a1b039868d5fadb115d6d2250786175b0))
- add gitleaks to project ([`b28f69e`](https://github.com/Larmeal/pylos/commit/b28f69e90257352d47701c0f24e9bf2cb608e726))
- add Yamloader ([`05dbc1a`](https://github.com/Larmeal/pylos/commit/05dbc1ab25a318c34039f3ad7ae2679750d28953))

### Fix

- **planner**: use the singular in the plan summary for one expectation ([`0fb34e3`](https://github.com/Larmeal/pylos/commit/0fb34e34fe11abb9d3139ec79bbddf3d6b5b54f1))
- extend gitleaks default rules ([`8c1bed8`](https://github.com/Larmeal/pylos/commit/8c1bed8645829ab3e767e2907a33da5c833d16e3))

### Refactor

- rename dict_deep_merge to dict_replace_by_key ([`bbd5d4d`](https://github.com/Larmeal/pylos/commit/bbd5d4d018a1fb4ca0ec1e25721d441bba5bc406))
- rename package from cosmos to pylos ([`3f7bdf4`](https://github.com/Larmeal/pylos/commit/3f7bdf4fe06dc9c593cd1fd766807ecc9a4fbaf3))
