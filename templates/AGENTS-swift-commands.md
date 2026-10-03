
## Tooling

# <<XCODEGEN_PROJECT_NOTE>>

```sh
# <<XCODEGEN_GENERATE_STEP>>
xcodebuild test -scheme __SCHEME__ -destination "__DESTINATION_EXAMPLE__"
swift-format lint --recursive --strict .
```

Run `swift-format format --recursive --in-place .` after changing any Swift file.
