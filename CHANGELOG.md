# Changelog

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
