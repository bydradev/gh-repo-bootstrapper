# Changelog

## [0.21.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.21.0...v0.21.1) (2026-10-26)


### Bug Fixes

* **templates:** read the pull request from the event file in the title check ([#191](https://github.com/bydradev/gh-repo-bootstrapper/issues/191)) ([085d662](https://github.com/bydradev/gh-repo-bootstrapper/commit/085d66213a1723b29d8547237579890473aa4057))

## [0.21.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.20.1...v0.21.0) (2026-10-25)


### Features

* keep a managed block of .gitignore and .prettierignore in step on adopt ([#190](https://github.com/bydradev/gh-repo-bootstrapper/issues/190)) ([159af34](https://github.com/bydradev/gh-repo-bootstrapper/commit/159af34eb7d2604e0d88736cc520d81d0d926b8c))
* review the security.txt expiry in the weekly baseline review ([#189](https://github.com/bydradev/gh-repo-bootstrapper/issues/189)) ([f95f45c](https://github.com/bydradev/gh-repo-bootstrapper/commit/f95f45c1445c7a5322dbb023401bb29fc0e71f03))
* turn on secret scanning, CodeQL and fork-run approval for public repositories ([#187](https://github.com/bydradev/gh-repo-bootstrapper/issues/187)) ([41acd8c](https://github.com/bydradev/gh-repo-bootstrapper/commit/41acd8c27d8bbf79aa6ee3864a45600510a4c3d7)), closes [#183](https://github.com/bydradev/gh-repo-bootstrapper/issues/183)

## [0.20.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.20.0...v0.20.1) (2026-10-24)


### Bug Fixes

* point messages that cite the readme at the new docs pages ([339110a](https://github.com/bydradev/gh-repo-bootstrapper/commit/339110a7ef5541469fbd9dafdb12dd4d8c776e9b))

## [0.20.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.19.2...v0.20.0) (2026-10-23)


### Features

* **configure-only:** ask before changing pr creation and dependabot alerts ([2f6c0c6](https://github.com/bydradev/gh-repo-bootstrapper/commit/2f6c0c6381873049ce49f5d9f1973db06df0584a))
* limit pull requests to collaborators and require conversation resolution on new repositories ([#177](https://github.com/bydradev/gh-repo-bootstrapper/issues/177)) ([2f6c0c6](https://github.com/bydradev/gh-repo-bootstrapper/commit/2f6c0c6381873049ce49f5d9f1973db06df0584a))
* list the github settings that have no api after creation ([2f6c0c6](https://github.com/bydradev/gh-repo-bootstrapper/commit/2f6c0c6381873049ce49f5d9f1973db06df0584a))
* turn on dependabot alerts on new repositories ([2f6c0c6](https://github.com/bydradev/gh-repo-bootstrapper/commit/2f6c0c6381873049ce49f5d9f1973db06df0584a))

## [0.19.2](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.19.1...v0.19.2) (2026-10-23)


### Bug Fixes

* read the releases for the seed digest table with a timeout and no lazy fetch ([#175](https://github.com/bydradev/gh-repo-bootstrapper/issues/175)) ([f7a810e](https://github.com/bydradev/gh-repo-bootstrapper/commit/f7a810e6b4623cf41ba6d40cd51269f018ef247b))

## [0.19.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.19.0...v0.19.1) (2026-10-23)


### Bug Fixes

* check the target folder before the prompts and default the destination ([#159](https://github.com/bydradev/gh-repo-bootstrapper/issues/159)) ([e1309fc](https://github.com/bydradev/gh-repo-bootstrapper/commit/e1309fc15672dd8e3c009a3c10aa79e1b53e696f))
* keep git show from fetching missing objects in a partial clone ([#174](https://github.com/bydradev/gh-repo-bootstrapper/issues/174)) ([e1f2957](https://github.com/bydradev/gh-repo-bootstrapper/commit/e1f29571ec61c381de4d9ea74486783ff67b9e98))
* name the real cause when git or the file system refuses a read ([#158](https://github.com/bydradev/gh-repo-bootstrapper/issues/158)) ([0931cf8](https://github.com/bydradev/gh-repo-bootstrapper/commit/0931cf88db0f29e2e313d1f939d3b77327514aa1))
* pin create-github-app-token v3.3.0 in the release templates ([#171](https://github.com/bydradev/gh-repo-bootstrapper/issues/171)) ([ac6e22c](https://github.com/bydradev/gh-repo-bootstrapper/commit/ac6e22cd39e2fa29d28fbd482557b2e9fc312ca0))
* read the body with github's squash trailers in the user-visible check ([#168](https://github.com/bydradev/gh-repo-bootstrapper/issues/168)) ([5f8f4e1](https://github.com/bydradev/gh-repo-bootstrapper/commit/5f8f4e1b17aed8ff009f52fe0b2e03a0ae096b5d))
* refuse an agents file with an early duplicate project specifics heading ([#164](https://github.com/bydradev/gh-repo-bootstrapper/issues/164)) ([590317c](https://github.com/bydradev/gh-repo-bootstrapper/commit/590317ce3b4bbc484dc819e5d78f223a6af0c422))
* reject an empty dash item in a flow sequence ([#167](https://github.com/bydradev/gh-repo-bootstrapper/issues/167)) ([4c058b2](https://github.com/bydradev/gh-repo-bootstrapper/commit/4c058b26e86567e5c426d5faf827bff97eedcd39))
* say that a footer-only release needs the override block ([#172](https://github.com/bydradev/gh-repo-bootstrapper/issues/172)) ([67667cc](https://github.com/bydradev/gh-repo-bootstrapper/commit/67667cca554e5be47540b219a13128835777ecbb))
* skip the workflow diff when no release tag holds a bootstrapper template ([#163](https://github.com/bydradev/gh-repo-bootstrapper/issues/163)) ([05a3fb8](https://github.com/bydradev/gh-repo-bootstrapper/commit/05a3fb8374c3bd35b5ac70a264ccdaec4d04cfab))
* stop waiting on a hung git show when building diff bases ([#160](https://github.com/bydradev/gh-repo-bootstrapper/issues/160)) ([fc58636](https://github.com/bydradev/gh-repo-bootstrapper/commit/fc58636e6b815dca9a6741249a16cb11eca757ac))

## [0.19.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.18.0...v0.19.0) (2026-10-23)


### Features

* show whether test.yml carries the postgres block in the check report ([#165](https://github.com/bydradev/gh-repo-bootstrapper/issues/165)) ([8310ff9](https://github.com/bydradev/gh-repo-bootstrapper/commit/8310ff95cf711fd46c9633eb3d6ad10e0380bc73))


### Bug Fixes

* add the other-type state and align the check report columns ([#155](https://github.com/bydradev/gh-repo-bootstrapper/issues/155)) ([8ecbfb0](https://github.com/bydradev/gh-repo-bootstrapper/commit/8ecbfb060b81cafc7e8a7478d766d492a7d58bfd))
* refresh dated tool and harness citations ([#161](https://github.com/bydradev/gh-repo-bootstrapper/issues/161)) ([994bda2](https://github.com/bydradev/gh-repo-bootstrapper/commit/994bda2fd8915ba3f79137dddd8280bdc1d32ca9))

## [0.18.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.17.2...v0.18.0) (2026-10-22)


### Features

* point nextjs agents at the playwright cli for browser checks ([#153](https://github.com/bydradev/gh-repo-bootstrapper/issues/153)) ([9912928](https://github.com/bydradev/gh-repo-bootstrapper/commit/99129288671b31f0565154df7924b565aa00cdbe))

## [0.17.2](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.17.1...v0.17.2) (2026-10-22)


### Bug Fixes

* check the pr body as github wraps it for the squash commit ([#151](https://github.com/bydradev/gh-repo-bootstrapper/issues/151)) ([198b36f](https://github.com/bydradev/gh-repo-bootstrapper/commit/198b36fce798287fbc0889dbdd46ee6a83843b16))

## [0.17.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.17.0...v0.17.1) (2026-10-22)


### Bug Fixes

* cite the open opencode issue and add the shell permission key ([#149](https://github.com/bydradev/gh-repo-bootstrapper/issues/149)) ([f8f984e](https://github.com/bydradev/gh-repo-bootstrapper/commit/f8f984e286baa00670c7ff1ffa55ab7005046b2c))
* make the opencode reviewer ask before reading outside the project ([f8f984e](https://github.com/bydradev/gh-repo-bootstrapper/commit/f8f984e286baa00670c7ff1ffa55ab7005046b2c))

## [0.17.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.16.1...v0.17.0) (2026-10-22)


### Features

* set bump-minor-pre-major in generated release please configs ([#144](https://github.com/bydradev/gh-repo-bootstrapper/issues/144)) ([e89dab3](https://github.com/bydradev/gh-repo-bootstrapper/commit/e89dab32d1bbcba0f347d9e5aef9dc3f48dcd7d9))


### Bug Fixes

* keep template-owned workflows out of prettier in next.js repositories ([#142](https://github.com/bydradev/gh-repo-bootstrapper/issues/142)) ([b1c4ddc](https://github.com/bydradev/gh-repo-bootstrapper/commit/b1c4ddcdcf68ae8b9ecef573e012f15294dd2502))
* make the lint baseline's max-warnings gate a scaffold requirement ([#143](https://github.com/bydradev/gh-repo-bootstrapper/issues/143)) ([4a360ac](https://github.com/bydradev/gh-repo-bootstrapper/commit/4a360ac041821e12fda59296472764693cb7f96c))
* require a dependency manifest before setup-python in the python test lane ([#147](https://github.com/bydradev/gh-repo-bootstrapper/issues/147)) ([d4e4947](https://github.com/bydradev/gh-repo-bootstrapper/commit/d4e494724a4d391baf3aaf1ad8861e6fccf99027))
* run the release guard with the workflow token ([#145](https://github.com/bydradev/gh-repo-bootstrapper/issues/145)) ([9d37b52](https://github.com/bydradev/gh-repo-bootstrapper/commit/9d37b5273245fe0ea86f7c1462639b7ed4c07b57))
* track the next.js 16.4 heading in the agent block ([#146](https://github.com/bydradev/gh-repo-bootstrapper/issues/146)) ([25b8f7d](https://github.com/bydradev/gh-repo-bootstrapper/commit/25b8f7d3646bd53e44512a1d0c3b1ce39c2855be))

## [0.16.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.16.0...v0.16.1) (2026-10-21)


### Bug Fixes

* accept quoted items in flow sequences and name the line the yaml reader refuses ([#140](https://github.com/bydradev/gh-repo-bootstrapper/issues/140)) ([015d4ef](https://github.com/bydradev/gh-repo-bootstrapper/commit/015d4ef77e713e11326fc5e9ac6de1be8d388261))
* diff a local-modified workflow against the nearest release after v0.8.1 too ([#136](https://github.com/bydradev/gh-repo-bootstrapper/issues/136)) ([75b99ee](https://github.com/bydradev/gh-repo-bootstrapper/commit/75b99ee7fd7c8ae4193f6e6679661a97fdf76ae3))
* name the cause in four adopt and check refusals ([#138](https://github.com/bydradev/gh-repo-bootstrapper/issues/138)) ([ebcc92d](https://github.com/bydradev/gh-repo-bootstrapper/commit/ebcc92d907c959b5abec5a447e37c2ee74dfbdf4))
* refuse the agents.md rebuild when a generated heading is duplicated ([#135](https://github.com/bydradev/gh-repo-bootstrapper/issues/135)) ([66fe1e8](https://github.com/bydradev/gh-repo-bootstrapper/commit/66fe1e82f270320e4d0d5ead15de291a93b9da67))
* refuse to delete an orphaned template file git does not track ([#137](https://github.com/bydradev/gh-repo-bootstrapper/issues/137)) ([268f5b5](https://github.com/bydradev/gh-repo-bootstrapper/commit/268f5b54e25e097bf0738b83e3e57c872808e25c))
* report an unsearchable directory as unreadable instead of crashing ([#139](https://github.com/bydradev/gh-repo-bootstrapper/issues/139)) ([030ec3b](https://github.com/bydradev/gh-repo-bootstrapper/commit/030ec3bbd44842829db76b04703369bc9b4f67f8))

## [0.16.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.15.3...v0.16.0) (2026-10-21)


### Features

* bring unedited nextjs baseline scripts up to date with --adopt ([#131](https://github.com/bydradev/gh-repo-bootstrapper/issues/131)) ([a41a172](https://github.com/bydradev/gh-repo-bootstrapper/commit/a41a172fa0f58cbef1ad957948470a6bbda353b8))
* record shared vendored-skill corrections in every repository that vendors the skill ([#133](https://github.com/bydradev/gh-repo-bootstrapper/issues/133)) ([125275a](https://github.com/bydradev/gh-repo-bootstrapper/commit/125275a175d6cb7f61b6f9649aec5db42d93a9a7))


### Bug Fixes

* tell the baseline review to reassess a row before dismissing its open alert ([#134](https://github.com/bydradev/gh-repo-bootstrapper/issues/134)) ([ebc637b](https://github.com/bydradev/gh-repo-bootstrapper/commit/ebc637b965b6e371858e18826ead81ef8dda2dd0))

## [0.15.3](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.15.2...v0.15.3) (2026-10-20)


### Bug Fixes

* stop failing the baseline review for advisory rows with no alert to dismiss ([#129](https://github.com/bydradev/gh-repo-bootstrapper/issues/129)) ([eea669a](https://github.com/bydradev/gh-repo-bootstrapper/commit/eea669a9607322d474906c2c94e1ffcb1f12b633))

## [0.15.2](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.15.1...v0.15.2) (2026-10-20)


### Bug Fixes

* keep skill files that ship inside a dependency out of the vendored-skill rules ([#127](https://github.com/bydradev/gh-repo-bootstrapper/issues/127)) ([1952e0d](https://github.com/bydradev/gh-repo-bootstrapper/commit/1952e0d64a94185621faa5842f5aee27b7eaf0a6))
* send agents to verify-external-claims before they add or update a third-party skill ([1952e0d](https://github.com/bydradev/gh-repo-bootstrapper/commit/1952e0d64a94185621faa5842f5aee27b7eaf0a6))

## [0.15.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.15.0...v0.15.1) (2026-10-20)


### Bug Fixes

* cite the source for the skills 1.7.4 ref-pinning example ([bb6cf9c](https://github.com/bydradev/gh-repo-bootstrapper/commit/bb6cf9c418a6902b8b7f78c1504aec45f88f790d))
* keep a vendored-skill correction until a refresh brings in the upstream fix ([bb6cf9c](https://github.com/bydradev/gh-repo-bootstrapper/commit/bb6cf9c418a6902b8b7f78c1504aec45f88f790d))
* limit the vendored-skill rules to skills installed in the repository ([#125](https://github.com/bydradev/gh-repo-bootstrapper/issues/125)) ([bb6cf9c](https://github.com/bydradev/gh-repo-bootstrapper/commit/bb6cf9c418a6902b8b7f78c1504aec45f88f790d))

## [0.15.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.14.1...v0.15.0) (2026-10-20)


### Features

* tell agents to keep vendored third-party skills under review ([#123](https://github.com/bydradev/gh-repo-bootstrapper/issues/123)) ([8318cb4](https://github.com/bydradev/gh-repo-bootstrapper/commit/8318cb4538f3436e053e763626d45fd886fc52bb))

## [0.14.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.14.0...v0.14.1) (2026-10-19)


### Bug Fixes

* report a details tag that Release Please cannot read back ([#121](https://github.com/bydradev/gh-repo-bootstrapper/issues/121)) ([4ca4b92](https://github.com/bydradev/gh-repo-bootstrapper/commit/4ca4b928e43abcd49eabdd79a7c3d6dd9308d5c2))
* report an entry scope that Release Please cannot parse ([4ca4b92](https://github.com/bydradev/gh-repo-bootstrapper/commit/4ca4b928e43abcd49eabdd79a7c3d6dd9308d5c2))

## [0.14.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.13.2...v0.14.0) (2026-10-19)


### Features

* generate a pull request template that asks for the user-visible line ([#120](https://github.com/bydradev/gh-repo-bootstrapper/issues/120)) ([b9cce50](https://github.com/bydradev/gh-repo-bootstrapper/commit/b9cce5066486faf2cab2d9e9e07454f8736fe480))
* require a user-visible yes/no line in pull request bodies ([#118](https://github.com/bydradev/gh-repo-bootstrapper/issues/118)) ([02d8777](https://github.com/bydradev/gh-repo-bootstrapper/commit/02d87773d52e8dab6efce6cc525a729238585d2d))

## [0.13.2](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.13.1...v0.13.2) (2026-10-18)


### Bug Fixes

* have reviewers re-check another reviewer's open blocking findings ([#115](https://github.com/bydradev/gh-repo-bootstrapper/issues/115)) ([8dfbb1a](https://github.com/bydradev/gh-repo-bootstrapper/commit/8dfbb1a51b8aad656e0d74e9cdd441045cd80779))

## [0.13.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.13.0...v0.13.1) (2026-10-18)


### Bug Fixes

* have the cross-family recipe follow the base branch's review-guidelines ([#113](https://github.com/bydradev/gh-repo-bootstrapper/issues/113)) ([c20b98c](https://github.com/bydradev/gh-repo-bootstrapper/commit/c20b98c252114f09b83100d13573d20352110b3b))
* make clear that the author's evidence is what withdraws a disputed finding ([c20b98c](https://github.com/bydradev/gh-repo-bootstrapper/commit/c20b98c252114f09b83100d13573d20352110b3b))
* name xcodegen generate only for repositories that use XcodeGen ([c20b98c](https://github.com/bydradev/gh-repo-bootstrapper/commit/c20b98c252114f09b83100d13573d20352110b3b))

## [0.13.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.12.1...v0.13.0) (2026-10-18)


### Features

* add a review-guidelines skill for the reviewer agents ([#111](https://github.com/bydradev/gh-repo-bootstrapper/issues/111)) ([d4b8ff8](https://github.com/bydradev/gh-repo-bootstrapper/commit/d4b8ff87fee205b5be8154a6ed4824c5b631fd0f))
* give every skill a row in the AGENTS.md skills table ([d4b8ff8](https://github.com/bydradev/gh-repo-bootstrapper/commit/d4b8ff87fee205b5be8154a6ed4824c5b631fd0f))

## [0.12.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.12.0...v0.12.1) (2026-10-18)


### Bug Fixes

* keep the word secrets out of release please workflow comments ([dfbe3c1](https://github.com/bydradev/gh-repo-bootstrapper/commit/dfbe3c1f1bd38302a29ff8d621394e46ce5a9f73))
* remove em dashes from the generated files ([#109](https://github.com/bydradev/gh-repo-bootstrapper/issues/109)) ([d5d9d4e](https://github.com/bydradev/gh-repo-bootstrapper/commit/d5d9d4eb71312c1c9e1bb9fa5c17a18b7f438a50))
* report a release skipped for missing credentials in the baseline review ([#106](https://github.com/bydradev/gh-repo-bootstrapper/issues/106)) ([dfbe3c1](https://github.com/bydradev/gh-repo-bootstrapper/commit/dfbe3c1f1bd38302a29ff8d621394e46ce5a9f73))

## [0.12.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.11.1...v0.12.0) (2026-10-17)


### Features

* add a public-site-indexing skill for Next.js repositories ([54994c4](https://github.com/bydradev/gh-repo-bootstrapper/commit/54994c43febe9fff93ae92e5116ada6f556a7d28))
* add an autonomy and escalation section to the generated agents.md ([#97](https://github.com/bydradev/gh-repo-bootstrapper/issues/97)) ([abae5e2](https://github.com/bydradev/gh-repo-bootstrapper/commit/abae5e225c94496428d6d0b188bcd79ac3731a05))
* generate docs/current-work.md for dated repository status ([abae5e2](https://github.com/bydradev/gh-repo-bootstrapper/commit/abae5e225c94496428d6d0b188bcd79ac3731a05))
* generate the screenshot-review skill only with --screenshots ([#100](https://github.com/bydradev/gh-repo-bootstrapper/issues/100)) ([f7a6d76](https://github.com/bydradev/gh-repo-bootstrapper/commit/f7a6d76faf2e2671666b079fdda3c797c3d93bd3))


### Bug Fixes

* count a screenshot file with a damaged stamp as the template's copy ([#103](https://github.com/bydradev/gh-repo-bootstrapper/issues/103)) ([bef1a90](https://github.com/bydradev/gh-repo-bootstrapper/commit/bef1a90485b12e70ec7a0ffc86a269f5b247ceb9))
* remove the OpenCode reviewer's built-in edit, subagent and shell tools ([54994c4](https://github.com/bydradev/gh-repo-bootstrapper/commit/54994c43febe9fff93ae92e5116ada6f556a7d28))
* remove unedited older-template guidance from project specifics on adopt ([abae5e2](https://github.com/bydradev/gh-repo-bootstrapper/commit/abae5e225c94496428d6d0b188bcd79ac3731a05))
* rewrite the branch-protection runbook as a short procedure ([#99](https://github.com/bydradev/gh-repo-bootstrapper/issues/99)) ([ced2b21](https://github.com/bydradev/gh-repo-bootstrapper/commit/ced2b21dc1bc4b7bf0003d52f646f4970d7d489f))
* skip the release with a warning when release please credentials are missing ([#98](https://github.com/bydradev/gh-repo-bootstrapper/issues/98)) ([d2b7d82](https://github.com/bydradev/gh-repo-bootstrapper/commit/d2b7d82dfa90a193b110cf3d94f4b33806066694))
* stop template skills stating facts about repository-owned files ([#101](https://github.com/bydradev/gh-repo-bootstrapper/issues/101)) ([54994c4](https://github.com/bydradev/gh-repo-bootstrapper/commit/54994c43febe9fff93ae92e5116ada6f556a7d28))

## [0.11.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.11.0...v0.11.1) (2026-10-16)


### Bug Fixes

* keep the generated baseline scripts prettier- and eslint-clean ([#95](https://github.com/bydradev/gh-repo-bootstrapper/issues/95)) ([418ddef](https://github.com/bydradev/gh-repo-bootstrapper/commit/418ddef29d74b2240c926c1534acc18d22d180f9))

## [0.11.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.10.0...v0.11.0) (2026-10-15)


### ⚠ BREAKING CHANGES

* require python 3.11 or newer

### Features

* accept outside pull requests with a dco sign-off check ([d309606](https://github.com/bydradev/gh-repo-bootstrapper/commit/d309606d8beae66bb8d89086e22876c3242791a9))
* license templates under mit-0 so generated files need no attribution ([d309606](https://github.com/bydradev/gh-repo-bootstrapper/commit/d309606d8beae66bb8d89086e22876c3242791a9))
* require python 3.11 or newer ([d309606](https://github.com/bydradev/gh-repo-bootstrapper/commit/d309606d8beae66bb8d89086e22876c3242791a9))
* wait seven days before dependabot proposes a new release in generated repositories ([013be9c](https://github.com/bydradev/gh-repo-bootstrapper/commit/013be9cdb37f661775e6f2142ad4ff2228867de6))


### Bug Fixes

* bring the bug report form in line with current flags and types ([6181a0e](https://github.com/bydradev/gh-repo-bootstrapper/commit/6181a0eab3336631afd1ec95616321ea64f49a70))
* check merge commits for a dco sign-off ([575c5e7](https://github.com/bydradev/gh-repo-bootstrapper/commit/575c5e7bbe81faa6029409296f6c01bbefb65c08))
* clone to an absolute path so a name starting with a dash is not a flag ([d035d24](https://github.com/bydradev/gh-repo-bootstrapper/commit/d035d24949f75810dc3a3915d38dfae3a8d6bd3b))
* count every lint suppression form the baseline check missed ([d3653c7](https://github.com/bydradev/gh-repo-bootstrapper/commit/d3653c7bb5143f6bc788d97acfd0b822d28743fe))
* drop stale deployment and e2e-prod references from templates ([6181a0e](https://github.com/bydradev/gh-repo-bootstrapper/commit/6181a0eab3336631afd1ec95616321ea64f49a70))
* explain a missing git in --check and --adopt instead of crashing ([d035d24](https://github.com/bydradev/gh-repo-bootstrapper/commit/d035d24949f75810dc3a3915d38dfae3a8d6bd3b))
* install a python dev group without building a project that is not a package ([#93](https://github.com/bydradev/gh-repo-bootstrapper/issues/93)) ([7c6c44f](https://github.com/bydradev/gh-repo-bootstrapper/commit/7c6c44fa427ca90c30df7a859e66a31bf9687270))
* install generated python ci dependencies from uv.lock ([#89](https://github.com/bydradev/gh-repo-bootstrapper/issues/89)) ([d3653c7](https://github.com/bydradev/gh-repo-bootstrapper/commit/d3653c7bb5143f6bc788d97acfd0b822d28743fe))
* print stale pin warnings as github annotations ([575c5e7](https://github.com/bydradev/gh-repo-bootstrapper/commit/575c5e7bbe81faa6029409296f6c01bbefb65c08))
* queue release runs so a newer push no longer cancels a release merge's run ([013be9c](https://github.com/bydradev/gh-repo-bootstrapper/commit/013be9cdb37f661775e6f2142ad4ff2228867de6))
* read the full release please app key when prompting ([#87](https://github.com/bydradev/gh-repo-bootstrapper/issues/87)) ([6181a0e](https://github.com/bydradev/gh-repo-bootstrapper/commit/6181a0eab3336631afd1ec95616321ea64f49a70))
* refuse a release please app key whose key data is cut or damaged ([7c6c44f](https://github.com/bydradev/gh-repo-bootstrapper/commit/7c6c44fa427ca90c30df7a859e66a31bf9687270))
* refuse agents.md rebuilds around an html block ([#94](https://github.com/bydradev/gh-repo-bootstrapper/issues/94)) ([575c5e7](https://github.com/bydradev/gh-repo-bootstrapper/commit/575c5e7bbe81faa6029409296f6c01bbefb65c08))
* refuse agents.md rebuilds the section parser cannot read safely ([#90](https://github.com/bydradev/gh-repo-bootstrapper/issues/90)) ([d035d24](https://github.com/bydradev/gh-repo-bootstrapper/commit/d035d24949f75810dc3a3915d38dfae3a8d6bd3b))
* refuse wrongly cased ghsa ids in the advisory baseline ([d3653c7](https://github.com/bydradev/gh-repo-bootstrapper/commit/d3653c7bb5143f6bc788d97acfd0b822d28743fe))
* reject a dependabot cooldown that excludes everything or uses unsupported keys ([575c5e7](https://github.com/bydradev/gh-repo-bootstrapper/commit/575c5e7bbe81faa6029409296f6c01bbefb65c08))
* report which github settings were applied when configuration fails ([d035d24](https://github.com/bydradev/gh-repo-bootstrapper/commit/d035d24949f75810dc3a3915d38dfae3a8d6bd3b))
* update the pinned xcodegen to 2.46.0 ([013be9c](https://github.com/bydradev/gh-repo-bootstrapper/commit/013be9cdb37f661775e6f2142ad4ff2228867de6))

## [0.10.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.9.0...v0.10.0) (2026-10-11)


### Features

* list kept action pins that differ from the template on adopt ([#83](https://github.com/bydradev/gh-repo-bootstrapper/issues/83)) ([f897838](https://github.com/bydradev/gh-repo-bootstrapper/commit/f897838ad04ce7029fe8dec4725be2b6dbf60636))


### Bug Fixes

* reject pr titles whose subject ends with a full stop ([#84](https://github.com/bydradev/gh-repo-bootstrapper/issues/84)) ([a9a8620](https://github.com/bydradev/gh-repo-bootstrapper/commit/a9a86209912ea017b396204833f61b99be52a3ba))

## [0.9.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.8.1...v0.9.0) (2026-10-10)


### Features

* make the pr title, release and baseline review workflows template-owned ([#80](https://github.com/bydradev/gh-repo-bootstrapper/issues/80)) ([96ff736](https://github.com/bydradev/gh-repo-bootstrapper/commit/96ff73662205c5199b0cebf79cef6b425a659972))

## [0.8.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.8.0...v0.8.1) (2026-10-09)


### Bug Fixes

* add job timeouts to generated and own workflows ([8c0721c](https://github.com/bydradev/gh-repo-bootstrapper/commit/8c0721cd4ceae23550b1701d45adb73294083a25))
* allow the rust actions the generated test workflow uses ([#70](https://github.com/bydradev/gh-repo-bootstrapper/issues/70)) ([8c0721c](https://github.com/bydradev/gh-repo-bootstrapper/commit/8c0721cd4ceae23550b1701d45adb73294083a25))
* ask before changing an existing repository's actions policy ([fc5f25e](https://github.com/bydradev/gh-repo-bootstrapper/commit/fc5f25e46b046f6b49bdde510f0b344fd626eff0))
* check every generated skill has a row in the hub's skills table ([0d589f5](https://github.com/bydradev/gh-repo-bootstrapper/commit/0d589f5ed291dc180cc1696a2f22892dcfa7fa30))
* check python formatting in the generated test workflow ([#77](https://github.com/bydradev/gh-repo-bootstrapper/issues/77)) ([0c3434a](https://github.com/bydradev/gh-repo-bootstrapper/commit/0c3434a2fef57b75e0203f17dc2c685ac1ed089c))
* check release-please branch titles unless the release bot opened them ([e2e6582](https://github.com/bydradev/gh-repo-bootstrapper/commit/e2e658258243aba7e832f50e85eb69ba240b915f))
* count only a real project specifics heading as the boundary ([0d589f5](https://github.com/bydradev/gh-repo-bootstrapper/commit/0d589f5ed291dc180cc1696a2f22892dcfa7fa30))
* install every default playwright browser for the full e2e run ([8c0721c](https://github.com/bydradev/gh-repo-bootstrapper/commit/8c0721cd4ceae23550b1701d45adb73294083a25))
* keep an existing repository's branch protection in configure-only ([#73](https://github.com/bydradev/gh-repo-bootstrapper/issues/73)) ([fc5f25e](https://github.com/bydradev/gh-repo-bootstrapper/commit/fc5f25e46b046f6b49bdde510f0b344fd626eff0))
* keep the github token out of generated workflow checkouts ([#79](https://github.com/bydradev/gh-repo-bootstrapper/issues/79)) ([e2e6582](https://github.com/bydradev/gh-repo-bootstrapper/commit/e2e658258243aba7e832f50e85eb69ba240b915f))
* list omo and shorten the hub's commit trailer examples ([0c3434a](https://github.com/bydradev/gh-repo-bootstrapper/commit/0c3434a2fef57b75e0203f17dc2c685ac1ed089c))
* pin the python ci tools in the generated test workflow ([8d83eaf](https://github.com/bydradev/gh-repo-bootstrapper/commit/8d83eaffd67fad56f6a2a78ac4330a2ef167866f))
* pin the rust toolchain action to a commit that stays on master ([e2e6582](https://github.com/bydradev/gh-repo-bootstrapper/commit/e2e658258243aba7e832f50e85eb69ba240b915f))
* read and write templates as utf-8 under any locale ([0d589f5](https://github.com/bydradev/gh-repo-bootstrapper/commit/0d589f5ed291dc180cc1696a2f22892dcfa7fa30))
* refuse adopt rewrites hidden by skip-worktree or assume-unchanged ([#72](https://github.com/bydradev/gh-repo-bootstrapper/issues/72)) ([65c63c1](https://github.com/bydradev/gh-repo-bootstrapper/commit/65c63c1ab30b43f70fcc212323932c0c712f154d))
* refuse adopt under a wrong type instead of deleting that type's skills ([#76](https://github.com/bydradev/gh-repo-bootstrapper/issues/76)) ([0d589f5](https://github.com/bydradev/gh-repo-bootstrapper/commit/0d589f5ed291dc180cc1696a2f22892dcfa7fa30))
* refuse deleting an orphan with uncommitted or staged changes ([65c63c1](https://github.com/bydradev/gh-repo-bootstrapper/commit/65c63c1ab30b43f70fcc212323932c0c712f154d))
* refuse orphan deletion when git cannot read the repository ([65c63c1](https://github.com/bydradev/gh-repo-bootstrapper/commit/65c63c1ab30b43f70fcc212323932c0c712f154d))
* refuse to tag a release merge whose own test run failed ([fc5f25e](https://github.com/bydradev/gh-repo-bootstrapper/commit/fc5f25e46b046f6b49bdde510f0b344fd626eff0))
* report a moved or missing next dev block ([0d589f5](https://github.com/bydradev/gh-repo-bootstrapper/commit/0d589f5ed291dc180cc1696a2f22892dcfa7fa30))
* report and remove dangling claude skill mirrors ([0d589f5](https://github.com/bydradev/gh-repo-bootstrapper/commit/0d589f5ed291dc180cc1696a2f22892dcfa7fa30))
* report symlinked skill folders that reuse a template skill name ([0d589f5](https://github.com/bydradev/gh-repo-bootstrapper/commit/0d589f5ed291dc180cc1696a2f22892dcfa7fa30))
* run creation git and gh commands without inherited repository overrides ([65c63c1](https://github.com/bydradev/gh-repo-bootstrapper/commit/65c63c1ab30b43f70fcc212323932c0c712f154d))
* run swift-format through xcrun in the swift hub and skill ([8c0721c](https://github.com/bydradev/gh-repo-bootstrapper/commit/8c0721cd4ceae23550b1701d45adb73294083a25))
* say nothing changed when adopt only kept or refused files ([457179e](https://github.com/bydradev/gh-repo-bootstrapper/commit/457179e4d7968cb8b8f65939f4db8be1bc368356))
* scope release-please app tokens to contents and pull requests ([8c0721c](https://github.com/bydradev/gh-repo-bootstrapper/commit/8c0721cd4ceae23550b1701d45adb73294083a25))
* stop adopt deleting a case-renamed live file as an orphan ([65c63c1](https://github.com/bydradev/gh-repo-bootstrapper/commit/65c63c1ab30b43f70fcc212323932c0c712f154d))
* stop the legacy digest walk at v0.6.0 ([8c0721c](https://github.com/bydradev/gh-repo-bootstrapper/commit/8c0721cd4ceae23550b1701d45adb73294083a25))
* validate the github owner like the repository name ([0d589f5](https://github.com/bydradev/gh-repo-bootstrapper/commit/0d589f5ed291dc180cc1696a2f22892dcfa7fa30))

## [0.8.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.7.0...v0.8.0) (2026-10-08)


### Features

* **templates:** add indexing guidance to the local-validation-nextjs skill ([#68](https://github.com/bydradev/gh-repo-bootstrapper/issues/68)) ([dacf40e](https://github.com/bydradev/gh-repo-bootstrapper/commit/dacf40e70d9d46407cdab555977ea81233db7bcf))

## [0.7.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.6.3...v0.7.0) (2026-10-06)


### Features

* route screenshot-review to repository skills and add the capture-lane review process ([#65](https://github.com/bydradev/gh-repo-bootstrapper/issues/65)) ([5636340](https://github.com/bydradev/gh-repo-bootstrapper/commit/563634031e7fd76e9b4fb44f1c3e82d69cb9ec70))

## [0.6.3](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.6.2...v0.6.3) (2026-10-05)


### Bug Fixes

* check for anchored symlink support before creating a new repo ([2281360](https://github.com/bydradev/gh-repo-bootstrapper/commit/22813602a592675e075dee14e7995bf7a286501a))
* place the template-owned stamp after BOM or CRLF frontmatter ([#61](https://github.com/bydradev/gh-repo-bootstrapper/issues/61)) ([2281360](https://github.com/bydradev/gh-repo-bootstrapper/commit/22813602a592675e075dee14e7995bf7a286501a))

## [0.6.2](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.6.1...v0.6.2) (2026-10-05)


### Bug Fixes

* tolerate missing git tags when diffing legacy template bodies ([#58](https://github.com/bydradev/gh-repo-bootstrapper/issues/58)) ([20cc2e8](https://github.com/bydradev/gh-repo-bootstrapper/commit/20cc2e8743a3655c44c59bae9e2bc113fd9c033c))

## [0.6.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.6.0...v0.6.1) (2026-10-05)


### Bug Fixes

* keep screenshot privacy and review gates in the AGENTS.md hub ([#56](https://github.com/bydradev/gh-repo-bootstrapper/issues/56)) ([50c9836](https://github.com/bydradev/gh-repo-bootstrapper/commit/50c98362e83d0c2c48b0ba0f855ef28598c003fc))

## [0.6.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.5.5...v0.6.0) (2026-10-03)


### Features

* generate read-only fresh-eyes reviewer agents ([59c02db](https://github.com/bydradev/gh-repo-bootstrapper/commit/59c02dbc0588bab426287bac5f2d4d525a08734a))
* split generated AGENTS.md into a hub and template-owned skills ([#54](https://github.com/bydradev/gh-repo-bootstrapper/issues/54)) ([59c02db](https://github.com/bydradev/gh-repo-bootstrapper/commit/59c02dbc0588bab426287bac5f2d4d525a08734a))
* track template-owned files with stamps in check and adopt ([59c02db](https://github.com/bydradev/gh-repo-bootstrapper/commit/59c02dbc0588bab426287bac5f2d4d525a08734a))
* validate the AGENTS.md budget, skill references and stamps ([59c02db](https://github.com/bydradev/gh-repo-bootstrapper/commit/59c02dbc0588bab426287bac5f2d4d525a08734a))


### Bug Fixes

* make generated markdown pass markdownlint ([#53](https://github.com/bydradev/gh-repo-bootstrapper/issues/53)) ([dc60eb3](https://github.com/bydradev/gh-repo-bootstrapper/commit/dc60eb39143cf99bb94d89018d8aca481b8e70f6))

## [0.5.5](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.5.4...v0.5.5) (2026-10-01)


### Bug Fixes

* read braced and comma-less eslint configuration comments ([#51](https://github.com/bydradev/gh-repo-bootstrapper/issues/51)) ([c76a9f2](https://github.com/bydradev/gh-repo-bootstrapper/commit/c76a9f28157025fa5398fcededc9d9adda750f2b))

## [0.5.4](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.5.3...v0.5.4) (2026-10-01)


### Bug Fixes

* declare shouldGroupImports in the swift-format template ([#49](https://github.com/bydradev/gh-repo-bootstrapper/issues/49)) ([2e511dd](https://github.com/bydradev/gh-repo-bootstrapper/commit/2e511dd29db021ffdcef53fb738e04435acd1c9e))
* say why the react dependabot group precedes dev-dependencies ([2e511dd](https://github.com/bydradev/gh-repo-bootstrapper/commit/2e511dd29db021ffdcef53fb738e04435acd1c9e))

## [0.5.3](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.5.2...v0.5.3) (2026-09-30)


### Bug Fixes

* stop strings from hiding eslint configuration comments ([#47](https://github.com/bydradev/gh-repo-bootstrapper/issues/47)) ([fa6e435](https://github.com/bydradev/gh-repo-bootstrapper/commit/fa6e435776d39e32c90e5142024b8ecedb0034b7))

## [0.5.2](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.5.1...v0.5.2) (2026-09-30)


### Bug Fixes

* count inline eslint rule configuration as a suppression ([#45](https://github.com/bydradev/gh-repo-bootstrapper/issues/45)) ([7cb4812](https://github.com/bydradev/gh-repo-bootstrapper/commit/7cb48124553b368967e44ee0966372ae8d1f4c5f))
* fail the production audit closed on an error response ([#44](https://github.com/bydradev/gh-repo-bootstrapper/issues/44)) ([fbe48c4](https://github.com/bydradev/gh-repo-bootstrapper/commit/fbe48c419c2bb8a27192f0345f7372b607d4f536))
* flag malformed review dates in the baseline review ([d1f7501](https://github.com/bydradev/gh-repo-bootstrapper/commit/d1f75016d2962d92aaab8eef9cc46ffaa41fffe5))
* name linked worktrees after their main checkout in --check and --adopt ([#42](https://github.com/bydradev/gh-repo-bootstrapper/issues/42)) ([5586544](https://github.com/bydradev/gh-repo-bootstrapper/commit/5586544a5a4c85be2bf4d90d1f6fd39ad82e9f92))
* treat an npm audit error as unknown in the baseline review ([#46](https://github.com/bydradev/gh-repo-bootstrapper/issues/46)) ([d1f7501](https://github.com/bydradev/gh-repo-bootstrapper/commit/d1f75016d2962d92aaab8eef9cc46ffaa41fffe5))

## [0.5.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.5.0...v0.5.1) (2026-09-30)


### Bug Fixes

* **scripts:** skip generated report directories in the baseline check ([#39](https://github.com/bydradev/gh-repo-bootstrapper/issues/39)) ([5f54b24](https://github.com/bydradev/gh-repo-bootstrapper/commit/5f54b24241b0a66acb3d85dc7ec704a25a1e464b))
* **templates:** describe the audit floor as any severity in the advisory baseline ([55e1530](https://github.com/bydradev/gh-repo-bootstrapper/commit/55e15303fe4eff0175eaeb968c537fb18b49f863))
* **templates:** document the Playwright reporter the e2e upload needs ([#37](https://github.com/bydradev/gh-repo-bootstrapper/issues/37)) ([55e1530](https://github.com/bydradev/gh-repo-bootstrapper/commit/55e15303fe4eff0175eaeb968c537fb18b49f863))

## [0.5.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.4.0...v0.5.0) (2026-09-29)


### Features

* add --check and --adopt for existing local repositories ([63ab9f5](https://github.com/bydradev/gh-repo-bootstrapper/commit/63ab9f59bcd14d79ab449805c2e181c10965262c))
* **templates:** add a rust repository type ([7202f75](https://github.com/bydradev/gh-repo-bootstrapper/commit/7202f754bf1a4e8c3514b973f1722ec3b778e036))

## [0.4.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.3.1...v0.4.0) (2026-09-21)


### Features

* **templates:** resolve the screenshot-review reference per repo type ([#23](https://github.com/bydradev/gh-repo-bootstrapper/issues/23)) ([124f3bf](https://github.com/bydradev/gh-repo-bootstrapper/commit/124f3bf50f429bc197ef74cebb8d3a2f1e3645a3))


### Bug Fixes

* **scripts:** classify a review due today as overdue, not upcoming ([#25](https://github.com/bydradev/gh-repo-bootstrapper/issues/25)) ([4283931](https://github.com/bydradev/gh-repo-bootstrapper/commit/4283931a5be7b1af7edd594a881633b020215fc9))

## [0.3.1](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.3.0...v0.3.1) (2026-08-24)


### Bug Fixes

* **gitignore:** correct xcscheme re-inclusion pattern ([0959389](https://github.com/bydradev/gh-repo-bootstrapper/commit/0959389625908f32c98c5cef161fbd96679031fa))
* **nextjs:** document macOS dev limits ([#16](https://github.com/bydradev/gh-repo-bootstrapper/issues/16)) ([d3a8c03](https://github.com/bydradev/gh-repo-bootstrapper/commit/d3a8c032305e0b6621eda0e8d0d4400db1ba0562))

## [0.3.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.2.0...v0.3.0) (2026-08-14)


### Features

* generate screenshot review guidance ([f33cdb6](https://github.com/bydradev/gh-repo-bootstrapper/commit/f33cdb6de0ebbaba18f96de52a7a72fe14d90c9b))

## [0.2.0](https://github.com/bydradev/gh-repo-bootstrapper/compare/v0.1.0...v0.2.0) (2026-08-14)


### Features

* **nextjs:** retire provider provisioning ([#3](https://github.com/bydradev/gh-repo-bootstrapper/issues/3)) ([7752548](https://github.com/bydradev/gh-repo-bootstrapper/commit/775254839d0a0d06e94782422c27777d6a72dd05))

## 0.1.0 (2026-08-09)


### Features

* initial public release ([529f31f](https://github.com/bydradev/gh-repo-bootstrapper/commit/529f31f9f5463a4224058a60f7adde17ecf79cc4))
