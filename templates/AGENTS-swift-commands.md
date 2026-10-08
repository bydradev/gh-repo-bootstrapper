
## Tooling

# <<XCODEGEN_PROJECT_NOTE>>

```sh
# <<XCODEGEN_GENERATE_STEP>>
xcodebuild test -scheme __SCHEME__ -destination "__DESTINATION_EXAMPLE__"
xcrun swift-format lint --recursive --strict .
```

Run `xcrun swift-format format --recursive --in-place .` after changing any Swift file.
