# Changelog

## [0.13.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.13.0...v0.13.1) (2026-10-18)


### Bug Fixes

* have the cross-family recipe follow the base branch's review-guidelines ([#113](https://github.com/bydradev/gh-repo-bootstrapper/issues/113)) ([b4c7364](https://github.com/bydradev/gh-repo-bootstrapper/commit/b4c7364e5ad45d5f3f7a47227815bc01047207a3))
* make clear that the author's evidence is what withdraws a disputed finding ([b4c7364](https://github.com/bydradev/gh-repo-bootstrapper/commit/b4c7364e5ad45d5f3f7a47227815bc01047207a3))
* name xcodegen generate only for repositories that use XcodeGen ([b4c7364](https://github.com/bydradev/gh-repo-bootstrapper/commit/b4c7364e5ad45d5f3f7a47227815bc01047207a3))

## [0.13.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.12.1...v0.13.0) (2026-10-18)


### Features

* add a review-guidelines skill for the reviewer agents ([#111](https://github.com/bydradev/gh-repo-bootstrapper/issues/111)) ([b73ef3f](https://github.com/bydradev/gh-repo-bootstrapper/commit/b73ef3f077930e69a9aa8bc47e95cc446b265891))
* give every skill a row in the AGENTS.md skills table ([b73ef3f](https://github.com/bydradev/gh-repo-bootstrapper/commit/b73ef3f077930e69a9aa8bc47e95cc446b265891))

## [0.12.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.12.0...v0.12.1) (2026-10-18)


### Bug Fixes

* keep the word secrets out of release please workflow comments ([700d228](https://github.com/bydradev/gh-repo-bootstrapper/commit/700d2289cf28d3c07bc3f3660ccdf4c5a34d543b))
* remove em dashes from the generated files ([#109](https://github.com/bydradev/gh-repo-bootstrapper/issues/109)) ([826b9a2](https://github.com/bydradev/gh-repo-bootstrapper/commit/826b9a2d036decb3be7a0efedc67edff5136dec5))
* report a release skipped for missing credentials in the baseline review ([#106](https://github.com/bydradev/gh-repo-bootstrapper/issues/106)) ([700d228](https://github.com/bydradev/gh-repo-bootstrapper/commit/700d2289cf28d3c07bc3f3660ccdf4c5a34d543b))

## [0.12.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.11.1...v0.12.0) (2026-10-17)


### Features

* add a public-site-indexing skill for Next.js repositories ([d1e1000](https://github.com/bydradev/gh-repo-bootstrapper/commit/d1e1000beb2997e7bb4f26827eb75840527243a4))
* add an autonomy and escalation section to the generated agents.md ([#97](https://github.com/bydradev/gh-repo-bootstrapper/issues/97)) ([54c394c](https://github.com/bydradev/gh-repo-bootstrapper/commit/54c394c09340100c03566ed9a4a57ba8f52f86e4))
* generate docs/current-work.md for dated repository status ([54c394c](https://github.com/bydradev/gh-repo-bootstrapper/commit/54c394c09340100c03566ed9a4a57ba8f52f86e4))
* generate the screenshot-review skill only with --screenshots ([#100](https://github.com/bydradev/gh-repo-bootstrapper/issues/100)) ([311f98b](https://github.com/bydradev/gh-repo-bootstrapper/commit/311f98bbc66765126e8d922eba307d5a3cd64d6a))


### Bug Fixes

* count a screenshot file with a damaged stamp as the template's copy ([#103](https://github.com/bydradev/gh-repo-bootstrapper/issues/103)) ([bd0d116](https://github.com/bydradev/gh-repo-bootstrapper/commit/bd0d116c48e8539fc5f4fddb29001162e6d59284))
* remove the OpenCode reviewer's built-in edit, subagent and shell tools ([d1e1000](https://github.com/bydradev/gh-repo-bootstrapper/commit/d1e1000beb2997e7bb4f26827eb75840527243a4))
* remove unedited older-template guidance from project specifics on adopt ([54c394c](https://github.com/bydradev/gh-repo-bootstrapper/commit/54c394c09340100c03566ed9a4a57ba8f52f86e4))
* rewrite the branch-protection runbook as a short procedure ([#99](https://github.com/bydradev/gh-repo-bootstrapper/issues/99)) ([50dcffa](https://github.com/bydradev/gh-repo-bootstrapper/commit/50dcffa4d6ffef6630f6772f130719736df0a77d))
* skip the release with a warning when release please credentials are missing ([#98](https://github.com/bydradev/gh-repo-bootstrapper/issues/98)) ([f0763b8](https://github.com/bydradev/gh-repo-bootstrapper/commit/f0763b8d75a0fc3bbc73ac085a2055766a14a787))
* stop template skills stating facts about repository-owned files ([#101](https://github.com/bydradev/gh-repo-bootstrapper/issues/101)) ([d1e1000](https://github.com/bydradev/gh-repo-bootstrapper/commit/d1e1000beb2997e7bb4f26827eb75840527243a4))

## [0.11.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.11.0...v0.11.1) (2026-10-16)


### Bug Fixes

* keep the generated baseline scripts prettier- and eslint-clean ([#95](https://github.com/bydradev/gh-repo-bootstrapper/issues/95)) ([48972f3](https://github.com/bydradev/gh-repo-bootstrapper/commit/48972f33c7b358ca0010f6bebef2b1f668e008ec))

## [0.11.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.10.0...v0.11.0) (2026-10-15)


### ⚠ BREAKING CHANGES

* require python 3.11 or newer

### Features

* accept outside pull requests with a dco sign-off check ([4404b30](https://github.com/bydradev/gh-repo-bootstrapper/commit/4404b30e5f2e1d61f1eecd2c0afd703ec0f2efae))
* license templates under mit-0 so generated files need no attribution ([4404b30](https://github.com/bydradev/gh-repo-bootstrapper/commit/4404b30e5f2e1d61f1eecd2c0afd703ec0f2efae))
* require python 3.11 or newer ([4404b30](https://github.com/bydradev/gh-repo-bootstrapper/commit/4404b30e5f2e1d61f1eecd2c0afd703ec0f2efae))
* wait seven days before dependabot proposes a new release in generated repositories ([20510ce](https://github.com/bydradev/gh-repo-bootstrapper/commit/20510ced416de4842685183f765770973cb626b7))


### Bug Fixes

* bring the bug report form in line with current flags and types ([4e2df47](https://github.com/bydradev/gh-repo-bootstrapper/commit/4e2df474387311107ab34a108d35d8cc1c0a4035))
* check merge commits for a dco sign-off ([4dba699](https://github.com/bydradev/gh-repo-bootstrapper/commit/4dba6992419ec78458d5c266e0a2c75cefa0033f))
* clone to an absolute path so a name starting with a dash is not a flag ([6c16271](https://github.com/bydradev/gh-repo-bootstrapper/commit/6c1627171c795258667465baffad530a01ff86cd))
* count every lint suppression form the baseline check missed ([b657013](https://github.com/bydradev/gh-repo-bootstrapper/commit/b6570134cb5528ab7713a7c0d0d4eaa8bf3099f0))
* drop stale deployment and e2e-prod references from templates ([4e2df47](https://github.com/bydradev/gh-repo-bootstrapper/commit/4e2df474387311107ab34a108d35d8cc1c0a4035))
* explain a missing git in --check and --adopt instead of crashing ([6c16271](https://github.com/bydradev/gh-repo-bootstrapper/commit/6c1627171c795258667465baffad530a01ff86cd))
* install a python dev group without building a project that is not a package ([#93](https://github.com/bydradev/gh-repo-bootstrapper/issues/93)) ([66ea487](https://github.com/bydradev/gh-repo-bootstrapper/commit/66ea487f44948407172698f26807ee61b41f0b16))
* install generated python ci dependencies from uv.lock ([#89](https://github.com/bydradev/gh-repo-bootstrapper/issues/89)) ([b657013](https://github.com/bydradev/gh-repo-bootstrapper/commit/b6570134cb5528ab7713a7c0d0d4eaa8bf3099f0))
* print stale pin warnings as github annotations ([4dba699](https://github.com/bydradev/gh-repo-bootstrapper/commit/4dba6992419ec78458d5c266e0a2c75cefa0033f))
* queue release runs so a newer push no longer cancels a release merge's run ([20510ce](https://github.com/bydradev/gh-repo-bootstrapper/commit/20510ced416de4842685183f765770973cb626b7))
* read the full release please app key when prompting ([#87](https://github.com/bydradev/gh-repo-bootstrapper/issues/87)) ([4e2df47](https://github.com/bydradev/gh-repo-bootstrapper/commit/4e2df474387311107ab34a108d35d8cc1c0a4035))
* refuse a release please app key whose key data is cut or damaged ([66ea487](https://github.com/bydradev/gh-repo-bootstrapper/commit/66ea487f44948407172698f26807ee61b41f0b16))
* refuse agents.md rebuilds around an html block ([#94](https://github.com/bydradev/gh-repo-bootstrapper/issues/94)) ([4dba699](https://github.com/bydradev/gh-repo-bootstrapper/commit/4dba6992419ec78458d5c266e0a2c75cefa0033f))
* refuse agents.md rebuilds the section parser cannot read safely ([#90](https://github.com/bydradev/gh-repo-bootstrapper/issues/90)) ([6c16271](https://github.com/bydradev/gh-repo-bootstrapper/commit/6c1627171c795258667465baffad530a01ff86cd))
* refuse wrongly cased ghsa ids in the advisory baseline ([b657013](https://github.com/bydradev/gh-repo-bootstrapper/commit/b6570134cb5528ab7713a7c0d0d4eaa8bf3099f0))
* reject a dependabot cooldown that excludes everything or uses unsupported keys ([4dba699](https://github.com/bydradev/gh-repo-bootstrapper/commit/4dba6992419ec78458d5c266e0a2c75cefa0033f))
* report which github settings were applied when configuration fails ([6c16271](https://github.com/bydradev/gh-repo-bootstrapper/commit/6c1627171c795258667465baffad530a01ff86cd))
* update the pinned xcodegen to 2.46.0 ([20510ce](https://github.com/bydradev/gh-repo-bootstrapper/commit/20510ced416de4842685183f765770973cb626b7))

## [0.10.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.9.0...v0.10.0) (2026-10-11)


### Features

* list kept action pins that differ from the template on adopt ([#83](https://github.com/bydradev/gh-repo-bootstrapper/issues/83)) ([e1e839c](https://github.com/bydradev/gh-repo-bootstrapper/commit/e1e839cb0467e5b09c4255f2003008c0056e233f))


### Bug Fixes

* reject pr titles whose subject ends with a full stop ([#84](https://github.com/bydradev/gh-repo-bootstrapper/issues/84)) ([09c92bf](https://github.com/bydradev/gh-repo-bootstrapper/commit/09c92bf4efb7038016917bd31b637cf15743bbe3))

## [0.9.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.8.1...v0.9.0) (2026-10-10)


### Features

* make the pr title, release and baseline review workflows template-owned ([#80](https://github.com/bydradev/gh-repo-bootstrapper/issues/80)) ([9ccc08e](https://github.com/bydradev/gh-repo-bootstrapper/commit/9ccc08ecc252eaf1deab4f6ecf56acc27b402585))

## [0.8.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.8.0...v0.8.1) (2026-10-09)


### Bug Fixes

* add job timeouts to generated and own workflows ([abe9958](https://github.com/bydradev/gh-repo-bootstrapper/commit/abe9958dae96bb71f749dd0010a7557d5947051d))
* allow the rust actions the generated test workflow uses ([#70](https://github.com/bydradev/gh-repo-bootstrapper/issues/70)) ([abe9958](https://github.com/bydradev/gh-repo-bootstrapper/commit/abe9958dae96bb71f749dd0010a7557d5947051d))
* ask before changing an existing repository's actions policy ([eab8141](https://github.com/bydradev/gh-repo-bootstrapper/commit/eab81414334bfcfffb84555b8751d5fe81ea02a1))
* check every generated skill has a row in the hub's skills table ([ce2aeda](https://github.com/bydradev/gh-repo-bootstrapper/commit/ce2aeda11cb85f1792b7361c72250e90694c52d5))
* check python formatting in the generated test workflow ([#77](https://github.com/bydradev/gh-repo-bootstrapper/issues/77)) ([52939a2](https://github.com/bydradev/gh-repo-bootstrapper/commit/52939a2bd2c271e0025235d9e776a385a8389afd))
* check release-please branch titles unless the release bot opened them ([6c036d8](https://github.com/bydradev/gh-repo-bootstrapper/commit/6c036d85282e3309f8e8dd14b1c401845b195ab5))
* count only a real project specifics heading as the boundary ([ce2aeda](https://github.com/bydradev/gh-repo-bootstrapper/commit/ce2aeda11cb85f1792b7361c72250e90694c52d5))
* install every default playwright browser for the full e2e run ([abe9958](https://github.com/bydradev/gh-repo-bootstrapper/commit/abe9958dae96bb71f749dd0010a7557d5947051d))
* keep an existing repository's branch protection in configure-only ([#73](https://github.com/bydradev/gh-repo-bootstrapper/issues/73)) ([eab8141](https://github.com/bydradev/gh-repo-bootstrapper/commit/eab81414334bfcfffb84555b8751d5fe81ea02a1))
* keep the github token out of generated workflow checkouts ([#79](https://github.com/bydradev/gh-repo-bootstrapper/issues/79)) ([6c036d8](https://github.com/bydradev/gh-repo-bootstrapper/commit/6c036d85282e3309f8e8dd14b1c401845b195ab5))
* list omo and shorten the hub's commit trailer examples ([52939a2](https://github.com/bydradev/gh-repo-bootstrapper/commit/52939a2bd2c271e0025235d9e776a385a8389afd))
* pin the python ci tools in the generated test workflow ([9a3316c](https://github.com/bydradev/gh-repo-bootstrapper/commit/9a3316c83a9904c71f395f014d3abf4b01ce88a4))
* pin the rust toolchain action to a commit that stays on master ([6c036d8](https://github.com/bydradev/gh-repo-bootstrapper/commit/6c036d85282e3309f8e8dd14b1c401845b195ab5))
* read and write templates as utf-8 under any locale ([ce2aeda](https://github.com/bydradev/gh-repo-bootstrapper/commit/ce2aeda11cb85f1792b7361c72250e90694c52d5))
* refuse adopt rewrites hidden by skip-worktree or assume-unchanged ([#72](https://github.com/bydradev/gh-repo-bootstrapper/issues/72)) ([54510c9](https://github.com/bydradev/gh-repo-bootstrapper/commit/54510c96ee201c98727fd3527ca0fe6f105321f3))
* refuse adopt under a wrong type instead of deleting that type's skills ([#76](https://github.com/bydradev/gh-repo-bootstrapper/issues/76)) ([ce2aeda](https://github.com/bydradev/gh-repo-bootstrapper/commit/ce2aeda11cb85f1792b7361c72250e90694c52d5))
* refuse deleting an orphan with uncommitted or staged changes ([54510c9](https://github.com/bydradev/gh-repo-bootstrapper/commit/54510c96ee201c98727fd3527ca0fe6f105321f3))
* refuse orphan deletion when git cannot read the repository ([54510c9](https://github.com/bydradev/gh-repo-bootstrapper/commit/54510c96ee201c98727fd3527ca0fe6f105321f3))
* refuse to tag a release merge whose own test run failed ([eab8141](https://github.com/bydradev/gh-repo-bootstrapper/commit/eab81414334bfcfffb84555b8751d5fe81ea02a1))
* report a moved or missing next dev block ([ce2aeda](https://github.com/bydradev/gh-repo-bootstrapper/commit/ce2aeda11cb85f1792b7361c72250e90694c52d5))
* report and remove dangling claude skill mirrors ([ce2aeda](https://github.com/bydradev/gh-repo-bootstrapper/commit/ce2aeda11cb85f1792b7361c72250e90694c52d5))
* report symlinked skill folders that reuse a template skill name ([ce2aeda](https://github.com/bydradev/gh-repo-bootstrapper/commit/ce2aeda11cb85f1792b7361c72250e90694c52d5))
* run creation git and gh commands without inherited repository overrides ([54510c9](https://github.com/bydradev/gh-repo-bootstrapper/commit/54510c96ee201c98727fd3527ca0fe6f105321f3))
* run swift-format through xcrun in the swift hub and skill ([abe9958](https://github.com/bydradev/gh-repo-bootstrapper/commit/abe9958dae96bb71f749dd0010a7557d5947051d))
* say nothing changed when adopt only kept or refused files ([3aebcd6](https://github.com/bydradev/gh-repo-bootstrapper/commit/3aebcd6d71b41650dcd16489afdb7be966b1daab))
* scope release-please app tokens to contents and pull requests ([abe9958](https://github.com/bydradev/gh-repo-bootstrapper/commit/abe9958dae96bb71f749dd0010a7557d5947051d))
* stop adopt deleting a case-renamed live file as an orphan ([54510c9](https://github.com/bydradev/gh-repo-bootstrapper/commit/54510c96ee201c98727fd3527ca0fe6f105321f3))
* stop the legacy digest walk at v0.6.0 ([abe9958](https://github.com/bydradev/gh-repo-bootstrapper/commit/abe9958dae96bb71f749dd0010a7557d5947051d))
* validate the github owner like the repository name ([ce2aeda](https://github.com/bydradev/gh-repo-bootstrapper/commit/ce2aeda11cb85f1792b7361c72250e90694c52d5))

## [0.8.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.7.0...v0.8.0) (2026-10-08)


### Features

* **templates:** add indexing guidance to the local-validation-nextjs skill ([#68](https://github.com/bydradev/gh-repo-bootstrapper/issues/68)) ([1746c55](https://github.com/bydradev/gh-repo-bootstrapper/commit/1746c557db1a3d7ae2bf59977853e329076b165c))

## [0.7.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.6.3...v0.7.0) (2026-10-06)


### Features

* route screenshot-review to repository skills and add the capture-lane review process ([#65](https://github.com/bydradev/gh-repo-bootstrapper/issues/65)) ([94a718c](https://github.com/bydradev/gh-repo-bootstrapper/commit/94a718ce90019b01d38423b2af11c43839bc7ecb))

## [0.6.3](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.6.2...v0.6.3) (2026-10-05)


### Bug Fixes

* check for anchored symlink support before creating a new repo ([5e3ced3](https://github.com/bydradev/gh-repo-bootstrapper/commit/5e3ced36a5639e3232840da340043720778d5b94))
* place the template-owned stamp after BOM or CRLF frontmatter ([#61](https://github.com/bydradev/gh-repo-bootstrapper/issues/61)) ([5e3ced3](https://github.com/bydradev/gh-repo-bootstrapper/commit/5e3ced36a5639e3232840da340043720778d5b94))

## [0.6.2](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.6.1...v0.6.2) (2026-10-05)


### Bug Fixes

* tolerate missing git tags when diffing legacy template bodies ([#58](https://github.com/bydradev/gh-repo-bootstrapper/issues/58)) ([2a9ed0c](https://github.com/bydradev/gh-repo-bootstrapper/commit/2a9ed0cda01c139cb6681c6d44b31d2984f04da8))

## [0.6.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.6.0...v0.6.1) (2026-10-05)


### Bug Fixes

* keep screenshot privacy and review gates in the AGENTS.md hub ([#56](https://github.com/bydradev/gh-repo-bootstrapper/issues/56)) ([fb5e295](https://github.com/bydradev/gh-repo-bootstrapper/commit/fb5e2956b4da23863c118d1863c8298154ebaca6))

## [0.6.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.5.5...v0.6.0) (2026-10-03)


### Features

* generate read-only fresh-eyes reviewer agents ([578591d](https://github.com/bydradev/gh-repo-bootstrapper/commit/578591d77aa4e97d09f9050fb7c63c6bd38abd9f))
* split generated AGENTS.md into a hub and template-owned skills ([#54](https://github.com/bydradev/gh-repo-bootstrapper/issues/54)) ([578591d](https://github.com/bydradev/gh-repo-bootstrapper/commit/578591d77aa4e97d09f9050fb7c63c6bd38abd9f))
* track template-owned files with stamps in check and adopt ([578591d](https://github.com/bydradev/gh-repo-bootstrapper/commit/578591d77aa4e97d09f9050fb7c63c6bd38abd9f))
* validate the AGENTS.md budget, skill references and stamps ([578591d](https://github.com/bydradev/gh-repo-bootstrapper/commit/578591d77aa4e97d09f9050fb7c63c6bd38abd9f))


### Bug Fixes

* make generated markdown pass markdownlint ([#53](https://github.com/bydradev/gh-repo-bootstrapper/issues/53)) ([fd09274](https://github.com/bydradev/gh-repo-bootstrapper/commit/fd09274ece482de26e6d05f18d87577bfb1eb711))

## [0.5.5](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.5.4...v0.5.5) (2026-10-01)


### Bug Fixes

* read braced and comma-less eslint configuration comments ([#51](https://github.com/bydradev/gh-repo-bootstrapper/issues/51)) ([d5e11c4](https://github.com/bydradev/gh-repo-bootstrapper/commit/d5e11c4b16560336f9f1f45f7894e0ae9c049944))

## [0.5.4](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.5.3...v0.5.4) (2026-10-01)


### Bug Fixes

* declare shouldGroupImports in the swift-format template ([#49](https://github.com/bydradev/gh-repo-bootstrapper/issues/49)) ([03056f4](https://github.com/bydradev/gh-repo-bootstrapper/commit/03056f453ab91c05e08e096080e610a609e26a66))
* say why the react dependabot group precedes dev-dependencies ([03056f4](https://github.com/bydradev/gh-repo-bootstrapper/commit/03056f453ab91c05e08e096080e610a609e26a66))

## [0.5.3](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.5.2...v0.5.3) (2026-09-30)


### Bug Fixes

* stop strings from hiding eslint configuration comments ([#47](https://github.com/bydradev/gh-repo-bootstrapper/issues/47)) ([ed3c6c4](https://github.com/bydradev/gh-repo-bootstrapper/commit/ed3c6c4d163d8dce6e32baba1fb6b560681d9d27))

## [0.5.2](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.5.1...v0.5.2) (2026-09-30)


### Bug Fixes

* count inline eslint rule configuration as a suppression ([#45](https://github.com/bydradev/gh-repo-bootstrapper/issues/45)) ([f5a8867](https://github.com/bydradev/gh-repo-bootstrapper/commit/f5a88679046551efa08adcd9e16ec5e900d5b4c2))
* fail the production audit closed on an error response ([#44](https://github.com/bydradev/gh-repo-bootstrapper/issues/44)) ([64e0469](https://github.com/bydradev/gh-repo-bootstrapper/commit/64e0469d798822d0d39ac18bc82ab81fd7ba267e))
* flag malformed review dates in the baseline review ([6d3cffe](https://github.com/bydradev/gh-repo-bootstrapper/commit/6d3cffef3cc3fa65c42f4420a483866cf4e49950))
* name linked worktrees after their main checkout in --check and --adopt ([#42](https://github.com/bydradev/gh-repo-bootstrapper/issues/42)) ([1643935](https://github.com/bydradev/gh-repo-bootstrapper/commit/16439353f60ac99df89339342cad14eb2d7afaf6))
* treat an npm audit error as unknown in the baseline review ([#46](https://github.com/bydradev/gh-repo-bootstrapper/issues/46)) ([6d3cffe](https://github.com/bydradev/gh-repo-bootstrapper/commit/6d3cffef3cc3fa65c42f4420a483866cf4e49950))

## [0.5.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.5.0...v0.5.1) (2026-09-30)


### Bug Fixes

* **scripts:** skip generated report directories in the baseline check ([#39](https://github.com/bydradev/gh-repo-bootstrapper/issues/39)) ([0fcae95](https://github.com/bydradev/gh-repo-bootstrapper/commit/0fcae95c61918139a781d47d12c690bd4bc476ba))
* **templates:** describe the audit floor as any severity in the advisory baseline ([7e73545](https://github.com/bydradev/gh-repo-bootstrapper/commit/7e7354506dd7f4093017d81e6d8a65cbb269ec4e))
* **templates:** document the Playwright reporter the e2e upload needs ([#37](https://github.com/bydradev/gh-repo-bootstrapper/issues/37)) ([7e73545](https://github.com/bydradev/gh-repo-bootstrapper/commit/7e7354506dd7f4093017d81e6d8a65cbb269ec4e))

## [0.5.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.4.0...v0.5.0) (2026-09-29)


### Features

* add --check and --adopt for existing local repositories ([3f3f130](https://github.com/bydradev/gh-repo-bootstrapper/commit/3f3f1300538e511bc6dc895faa822883875bdf83))
* **templates:** add a rust repository type ([757b2ad](https://github.com/bydradev/gh-repo-bootstrapper/commit/757b2ad8e14ac304c3b9e80c55a927ceb89db451))

## [0.4.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.3.1...v0.4.0) (2026-09-21)


### Features

* **templates:** resolve the screenshot-review reference per repo type ([#23](https://github.com/bydradev/gh-repo-bootstrapper/issues/23)) ([9e4ce2d](https://github.com/bydradev/gh-repo-bootstrapper/commit/9e4ce2d8e0cb63ce629bad8007c5bc9263d252be))


### Bug Fixes

* **scripts:** classify a review due today as overdue, not upcoming ([#25](https://github.com/bydradev/gh-repo-bootstrapper/issues/25)) ([e92bb9b](https://github.com/bydradev/gh-repo-bootstrapper/commit/e92bb9bf401cc44fa314032bfbbc549b580aa777))

## [0.3.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.3.0...v0.3.1) (2026-08-24)


### Bug Fixes

* **gitignore:** correct xcscheme re-inclusion pattern ([f0e6eac](https://github.com/bydradev/gh-repo-bootstrapper/commit/f0e6eac8a2f87e6a70240f8f35f8a9de983a003e))
* **nextjs:** document macOS dev limits ([#16](https://github.com/bydradev/gh-repo-bootstrapper/issues/16)) ([f44a524](https://github.com/bydradev/gh-repo-bootstrapper/commit/f44a524696c04ab25da415da5bce61a0d8e2445d))

## [0.3.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.2.0...v0.3.0) (2026-08-14)


### Features

* generate screenshot review guidance ([f33cdb6](https://github.com/bydradev/gh-repo-bootstrapper/commit/f33cdb6de0ebbaba18f96de52a7a72fe14d90c9b))

## [0.2.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.1.0...v0.2.0) (2026-08-14)


### Features

* **nextjs:** retire provider provisioning ([#3](https://github.com/bydradev/gh-repo-bootstrapper/issues/3)) ([7752548](https://github.com/bydradev/gh-repo-bootstrapper/commit/775254839d0a0d06e94782422c27777d6a72dd05))

## 0.1.0 (2026-08-09)


### Features

* initial public release ([529f31f](https://github.com/bydradev/gh-repo-bootstrapper/commit/529f31f9f5463a4224058a60f7adde17ecf79cc4))
