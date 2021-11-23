# Contributing to RUBEM

Thanks for your time and willingness to contribute to RUBEM! This page gives a few guidelines.

## General questions

Please do not use the issue tracker for support questions. You can send your questions, ideas and discussion issues to our [e-mail](mailto:rubem.hydrological@labsid.eng.br).

## Reporting Bugs and Requesting Features

Bugs and features requests are tracked on our GitHub [issue](https://github.com/LabSid-USP/RUBEM/issues) page.

If you have found a bug in the RUBEM software (or any other erroneous behavior) please file a bug report. Before reporting a bug or requesting a new feature on the [issue tracker](https://github.com/LabSid-USP/RUBEM/issues), consider these points:

- Check that someone hasn't already filed the bug or feature request by searching or running custom queries in the issue tracker;

- Don't use the issue page to ask support questions. Use the [support form](https://forms.gle/JmxWKoXh4C29V2rD8) for that;

- Don't reopen issues that have been marked "wontfix" without finding consensus to do so.

### Reporing bugs

Well-written bug reports are incredibly helpful. However, there’s a certain amount of overhead involved in working with any bug tracking system so your help in keeping our issue tracker as useful as possible is appreciated. In particular:

- Do read the [FAQ](https://rubem.readthedocs.io/en/latest/faq.html) to see if your issue might be a well-known question;

- Do ask on our [support form](https://forms.gle/JmxWKoXh4C29V2rD8) first if you're not sure if what you're seeing is a bug;

- Do write complete, reproducible, specific bug reports. You must include a clear, concise description of the problem, and a set of instructions for replicating it. Add as much debug information as you can: test cases, exception backtraces, screenshots, Python version, QGIS version, RUBEM version, details about the operating system used,  etc. A nice small test case is the best way to report a bug, as it gives us a helpful way to confirm the bug quickly;

### Reporing user interface bugs and features

If your bug or feature request touches on anything visual in nature, there are a few additional guidelines to follow:

- Include screenshots in your issue which are the visual equivalent of a minimal testcase. Show off the issue, not the customizations you’ve made to your QGIS;

- If the issue is difficult to show off using a still image, consider capturing a brief screencast. If your software permits it, capture only the relevant area of the screen.
If you're offering a patch which changes the look or behavior of RUBEM's UI, you must attach before and after screenshots/screencasts. Issues lacking these are difficult for triagers to assess quickly;

- Screenshots don't absolve you of other good reporting practices. Make sure to include step-by-step instructions on how to reproduce the behavior visible in the screenshots.
Make sure to set the UI/UX flag on the issue so interested parties can find your issue.

### Requesting features

We’re always trying to make RUBEM better, and your feature requests are a key part of that. Here are some tips on how to make a request most effectively:

- Make sure the feature actually requires changes in RUBEM Hydrlogical's core. If your idea can be developed as an independent application or module we'll probably suggest that you develop it independently;

- Describe clearly and concisely what the missing feature is and how you'd like to see it implemented. Include example code (non-functional is OK) if possible;

- Explain why you'd like the feature. Explaining a minimal use case will help others understand where it fits in, and if there are already other ways of achieving the same thing.
If there's a consensus agreement on the feature, then it's appropriate to create a issue;

As with most open-source projects, code talks. If you are willing to write the code for the feature yourself or, even better, if you’ve already written it, it’s much more likely to be accepted. Fork RUBEM on GitHub, create a feature branch, and show us your work!

## Pull requests

In case you can provide a code fix yourself please consider submitting a [pull](https://github.com/LabSid-USP/RUBEM/pulls) request.

For something that is bigger than a trivial fix follow these steps:

1. Create an issue describing the changes you intend to make.
2. Create your own fork of the RUBEM code.
3. Create a branch with the corresponding issue number.
4. Switch to that branch.
5. Apply your modifications.
6. Ensure cross-platform compatibility; for Linux, Mac, and Windows.

All contributions to this project will be released under the GPLv3 license under copyright of the RUBEM owners. By submitting a pull request:

- You are agreeing to comply with the waiver of your copyright interest;
- You state that the contribution was created in whole by you and you have the right to submit it.

## Contacting us

For other project related questions please contact us on our [support form](https://forms.gle/JmxWKoXh4C29V2rD8).
