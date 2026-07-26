# Illustrative output

The exact tiny-model wording varies by runtime. A completed run writes
`output/comparison.json` containing the shared prompt plus `before` and `after` text.

Expected behavioral check:

- the adapter directory reloads with `PeftModel.from_pretrained`;
- both generations complete;
- the after text can differ from the base output;
- no claim of quality improvement is made without a separate evaluation set.
