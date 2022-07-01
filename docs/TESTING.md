# E2E Testing

## Acceptance Tests

The acceptance tests are written using the screenplay technique provided by the library
[screenpy](https://github.com/perrygoy/screenpy), which is an open source library that enables the E2E
and API testing to be written in a more literal way to be more comprehensive.

### Configuration for local acceptance testing

In order to execute the tests locally you must download the driver that you are attempting to use
from the [selenium](https://www.selenium.dev/downloads/) website and store in `/usr/local/bin`.

Once you have done this you could try one of the following commands to verify that the driver is properly
installed.

```
## If you downloaded the Firefox driver
geckodriver -v

## If you downloaded the Chrome driver
chromedriver -v
```

If your terminal shows the corresponding version of the driver you downloaded you are ready to execute the
test cases locally.

You can switch the driver to be used in the execution in the `config.json` file.

### Execute tests locally

The tests cases are located in `/tests/acceptance/feature` and could be run with pytest using the following
command.

```
python -m pytest tests/acceptance/feature
```
