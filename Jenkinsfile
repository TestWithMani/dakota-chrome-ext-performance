pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '30'))
        timeout(time: 200, unit: 'MINUTES')
    }

    parameters {
        choice(
            name: 'TEST_SELECTION_MODE',
            choices: ['ALL_TESTS', 'SMOKE', 'CHECKBOX_SELECTION'],
            description: 'ALL_TESTS runs full performance suite, SMOKE runs search + login, CHECKBOX_SELECTION runs selected TEST_* checkboxes.'
        )
        booleanParam(
            name: 'FRESH_REPORT_OUTPUT',
            defaultValue: false,
            description: 'Clear old report artifacts before this run and generate fresh Excel + Allure output.'
        )
        booleanParam(
            name: 'RESET_JOB_BUILD_HISTORY',
            defaultValue: false,
            description: 'Safe mode: clean workspace report artifacts only (does not delete Jenkins build records).'
        )
        string(
            name: 'ADDITIONAL_EMAILS',
            defaultValue: '',
            description: 'Additional email recipients (comma-separated list).'
        )
        string(
            name: 'DEFAULT_EMAIL',
            defaultValue: 'usman.arshad@rolustech.com',
            description: 'Primary recipient for pipeline report emails.'
        )
        string(
            name: 'DAKOTA_CREDENTIALS_ID',
            defaultValue: 'dakota-portal-creds',
            description: 'Jenkins credential ID for Dakota portal login (DAKOTA_USERNAME / DAKOTA_PASSWORD).'
        )
        string(
            name: 'PYTHON_EXE',
            defaultValue: '',
            description: 'Optional full path to python.exe on the agent. Empty = auto-detect (py -3, python3, python).'
        )
        string(
            name: 'ALLURE_JENKINS_TOOL',
            defaultValue: '',
            description: 'Jenkins Allure Commandline tool name from Global Tool Configuration. Empty = default installation.'
        )
        booleanParam(
            name: 'ENABLE_INFRA_RETRY',
            defaultValue: true,
            description: 'Automatically retry only flaky/infrastructure Selenium failures.'
        )
        string(
            name: 'INFRA_RETRY_COUNT',
            defaultValue: '1',
            description: 'Maximum retries for allowed infra failures (0 disables retries).'
        )
        string(
            name: 'PARALLEL_WORKERS',
            defaultValue: '1',
            description: "Pytest xdist workers. Keep '1' for performance suite (shared session-scoped browser login)."
        )
        booleanParam(
            name: 'RUN_ALLURE',
            defaultValue: true,
            description: 'Generate and publish Allure report in Jenkins.'
        )
        booleanParam(
            name: 'SEND_EMAIL',
            defaultValue: true,
            description: 'Send HTML email summary after pipeline completion.'
        )
        booleanParam(name: 'TEST_SEARCH_TIME', defaultValue: false, description: 'Run company search timing test.')
        booleanParam(name: 'TEST_DETAIL_LOADING', defaultValue: false, description: 'Run company detail load timing test.')
        booleanParam(name: 'TEST_CONTACTS_LOADING', defaultValue: false, description: 'Run company contacts tab load timing test.')
        booleanParam(name: 'TEST_TAB_LOADING', defaultValue: false, description: 'Run company-type profile tab load timing test.')
        booleanParam(name: 'TEST_LOAD_MORE', defaultValue: false, description: 'Run search Load More timing test.')
        booleanParam(name: 'TEST_LOGIN', defaultValue: false, description: 'Run portal + extension login test.')
    }

    environment {
        VENV_DIR = '.venv-jenkins'
        DAKOTA_HEADLESS = '1'
        CI = 'true'
        PYTHONUNBUFFERED = '1'
        PIP_DISABLE_PIP_VERSION_CHECK = '1'
        PYTEST_JUNIT = 'test-results/pytest.xml'
        PYTEST_HTML = 'test-results/report.html'
        PYTEST_JSON = 'test-results/report.json'
        ALLURE_DIR = 'allure-results'
        EXCEL_REPORT = 'reports/dakota_chrome_extension_results.xlsx'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    if (!fileExists('requirements.txt')) {
                        error('Checkout failed — requirements.txt not found in repository.')
                    }
                    def shortCommit = env.GIT_COMMIT ? env.GIT_COMMIT.take(7) : 'N/A'
                    currentBuild.description = "Dakota Chrome Extension | ${params.TEST_SELECTION_MODE}"
                    echo "Repo: https://github.com/TestWithMani/dakota-chrome-ext-performance"
                    echo "Branch: ${env.BRANCH_NAME ?: 'main'} | Commit: ${shortCommit}"
                }
            }
        }

        stage('Resolve Python') {
            steps {
                script {
                    def pythonExeParam = (params.PYTHON_EXE ?: '').trim()
                    runShell(
                        """
                            set -e
                            BASE_PY=""
                            if [ -n "${pythonExeParam}" ] && [ -x "${pythonExeParam}" ]; then BASE_PY="${pythonExeParam}"; fi
                            if [ -z "\$BASE_PY" ] && command -v python3 >/dev/null 2>&1; then BASE_PY="\$(command -v python3)"; fi
                            if [ -z "\$BASE_PY" ] && command -v python >/dev/null 2>&1; then BASE_PY="\$(command -v python)"; fi
                            if [ -z "\$BASE_PY" ]; then echo "[ERROR] Python 3.10+ not found. Set PYTHON_EXE parameter."; exit 1; fi
                            echo "[INFO] Using Python: \$BASE_PY"
                            "\$BASE_PY" --version
                            echo "\$BASE_PY" > python_exe.txt
                        """,
                        """
                            @echo off
                            setlocal EnableDelayedExpansion
                            set "BASE_PY="
                            if not "${pythonExeParam}"=="" if exist "${pythonExeParam}" set "BASE_PY=${pythonExeParam}"
                            if not defined BASE_PY for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "BASE_PY=%%i"
                            if not defined BASE_PY for /f "delims=" %%i in ('where python 2^>nul') do if not defined BASE_PY set "BASE_PY=%%i"
                            if not defined BASE_PY (echo [ERROR] Python 3.10+ not found. & exit /b 1)
                            echo [INFO] Using Python: !BASE_PY!
                            "!BASE_PY!" --version
                            echo !BASE_PY!> python_exe.txt
                            endlocal
                        """
                    )
                    env.RESOLVED_PYTHON = readFile('python_exe.txt').trim()
                    echo "Resolved Python: ${env.RESOLVED_PYTHON}"
                }
            }
        }

        stage('Reset Build History (Optional)') {
            when {
                expression { return params.RESET_JOB_BUILD_HISTORY == true }
            }
            steps {
                echo 'Reset Build History is ENABLED but running SAFE mode (no Jenkins internal API usage).'
                script {
                    if (fileExists('test-results')) {
                        runShell('rm -rf test-results || true', 'rmdir /s /q test-results')
                    }
                    if (fileExists('allure-results')) {
                        runShell('rm -rf allure-results || true', 'rmdir /s /q allure-results')
                    }
                    if (fileExists('reports')) {
                        runShell(
                            'rm -f reports/dakota_chrome_extension_results.xlsx reports/.latest_dakota_search_report.txt || true',
                            'del /q reports\\dakota_chrome_extension_results.xlsx 2>nul & del /q reports\\.latest_dakota_search_report.txt 2>nul'
                        )
                    }
                    echo 'Workspace history reset completed safely.'
                }
            }
        }

        stage('Setup Python Environment') {
            steps {
                script {
                    runShell(
                        """
                            "${env.RESOLVED_PYTHON}" -m venv ${env.VENV_DIR}
                            ${env.VENV_DIR}/bin/python -m pip install --upgrade pip
                            ${env.VENV_DIR}/bin/python -m pip install -r requirements.txt
                            ${env.VENV_DIR}/bin/python -m pip install -r requirements-ci.txt
                        """,
                        """
                            "${env.RESOLVED_PYTHON}" -m venv %VENV_DIR%
                            %VENV_DIR%\\Scripts\\python -m pip install --upgrade pip
                            %VENV_DIR%\\Scripts\\python -m pip install -r requirements.txt
                            %VENV_DIR%\\Scripts\\python -m pip install -r requirements-ci.txt
                        """
                    )
                }
            }
        }

        stage('Download Extension') {
            steps {
                script {
                    runShell(
                        '${VENV_DIR}/bin/python download_extension.py',
                        '%VENV_DIR%\\Scripts\\python download_extension.py'
                    )
                }
            }
        }

        stage('Prepare Report Directories') {
            steps {
                script {
                    def effectiveCfg = getEffectiveRunConfig()
                    if (effectiveCfg.freshReportOutput) {
                        echo 'Fresh report mode enabled: clearing previous Excel and Allure history artifacts.'
                        runShell(
                            '''
                                rm -f reports/dakota_chrome_extension_results.xlsx || true
                                rm -f reports/.latest_dakota_search_report.txt || true
                                rm -rf allure-report || true
                            ''',
                            '''
                                if exist "reports\\dakota_chrome_extension_results.xlsx" del /q "reports\\dakota_chrome_extension_results.xlsx"
                                if exist "reports\\.latest_dakota_search_report.txt" del /q "reports\\.latest_dakota_search_report.txt"
                                if exist allure-report rmdir /s /q allure-report
                            '''
                        )
                    }
                    runShell(
                        '''
                            rm -rf test-results allure-results reports || true
                            mkdir -p test-results allure-results reports
                        ''',
                        '''
                            if exist test-results rmdir /s /q test-results
                            if exist allure-results rmdir /s /q allure-results
                            if not exist reports mkdir reports
                            mkdir test-results
                            mkdir allure-results
                        '''
                    )
                }
            }
        }

        stage('Static Validation') {
            steps {
                script {
                    def effectiveCfg = getEffectiveRunConfig()
                    validateRuntimeParameters(
                        effectiveCfg.testSelectionMode as String,
                        effectiveCfg.infraRetryCount as String,
                        params.PARALLEL_WORKERS as String
                    )
                    def selectedTestFiles = resolveSelectedTestFiles(
                        effectiveCfg.testSelectionMode as String,
                        params
                    )
                    echo "Selection mode -> ${effectiveCfg.testSelectionMode}"
                    echo "Selected ${selectedTestFiles.size()} test files."
                    runPytest('--version')
                    runPytest("--collect-only -q ${selectedTestFiles.join(' ')}")
                }
            }
        }

        stage('Run Tests') {
            steps {
                script {
                    def effectiveCfg = getEffectiveRunConfig()
                    def selectedTestFiles = resolveSelectedTestFiles(
                        effectiveCfg.testSelectionMode as String,
                        params
                    )
                    def runCmd = buildPytestCommand(
                        selectedTestFiles,
                        effectiveCfg.runAllure as boolean,
                        effectiveCfg.enableInfraRetry as boolean,
                        effectiveCfg.infraRetryCount as String,
                        params.PARALLEL_WORKERS as String
                    )
                    echo "Pytest command: pytest ${runCmd}"

                    withCredentials([usernamePassword(
                        credentialsId: "${params.DAKOTA_CREDENTIALS_ID}",
                        usernameVariable: 'DAKOTA_USERNAME',
                        passwordVariable: 'DAKOTA_PASSWORD'
                    )]) {
                        catchError(buildResult: 'FAILURE', stageResult: 'FAILURE') {
                            runPytest(runCmd)
                        }
                    }
                }
            }
        }

        stage('Publish Reports') {
            steps {
                script {
                    def effectiveCfg = getEffectiveRunConfig()
                    if (fileExists(env.PYTEST_JUNIT)) {
                        junit testResults: env.PYTEST_JUNIT, allowEmptyResults: true
                    }

                    try {
                        publishHTML(target: [
                            reportName: 'Pytest HTML Report',
                            reportDir: 'test-results',
                            reportFiles: 'report.html',
                            keepAll: true,
                            alwaysLinkToLastBuild: true,
                            allowMissing: true
                        ])
                    } catch (MissingMethodException ex) {
                        echo 'HTML Publisher plugin not installed; skipping publishHTML step.'
                    }

                    if (effectiveCfg.runAllure && fileExists(env.ALLURE_DIR)) {
                        def allureArgs = [
                            includeProperties: false,
                            jdk: '',
                            properties: [],
                            reportBuildPolicy: 'ALWAYS',
                            results: [[path: env.ALLURE_DIR]],
                            reportName: 'Allure Report'
                        ]
                        if (params.ALLURE_JENKINS_TOOL?.trim()) {
                            allureArgs.tool = params.ALLURE_JENKINS_TOOL.trim()
                        }
                        allure(allureArgs)
                    } else if (effectiveCfg.runAllure) {
                        echo "Skipping Allure publish: ${env.ALLURE_DIR} directory not found."
                    }
                }
            }
        }
    }

    post {
        always {
            script {
                def effectiveCfg = getEffectiveRunConfig()
                logTestSummaryToConsole('Post pipeline summary')
                if (fileExists('test-results')) {
                    archiveArtifacts artifacts: 'test-results/**', allowEmptyArchive: true
                }
                if (fileExists('allure-results')) {
                    archiveArtifacts artifacts: 'allure-results/**', allowEmptyArchive: true
                }
                def excelArtifact = prepareExcelArtifactPath()
                if (excelArtifact) {
                    archiveArtifacts artifacts: excelArtifact, allowEmptyArchive: true
                }
                if (effectiveCfg.sendEmail) {
                    sendEmailNotification(
                        currentBuild.currentResult ?: 'UNKNOWN',
                        effectiveCfg.defaultEmail as String,
                        effectiveCfg.additionalEmails as String
                    )
                }
            }
        }
    }
}

def getEffectiveRunConfig() {
    return [
        testSelectionMode: params.TEST_SELECTION_MODE as String,
        freshReportOutput: params.FRESH_REPORT_OUTPUT as boolean,
        additionalEmails : params.ADDITIONAL_EMAILS as String,
        defaultEmail     : params.DEFAULT_EMAIL as String,
        enableInfraRetry : params.ENABLE_INFRA_RETRY as boolean,
        infraRetryCount  : params.INFRA_RETRY_COUNT as String,
        runAllure        : params.RUN_ALLURE as boolean,
        sendEmail        : params.SEND_EMAIL as boolean,
    ]
}

def shellQuotePytestArgs(List parts) {
    parts.collect { arg ->
        if (!arg.contains(' ')) {
            return arg
        }
        return '"' + arg.replace('"', '""') + '"'
    }.join(' ')
}

def buildPytestCommand(
    List selectedTestFiles,
    boolean runAllure,
    boolean enableInfraRetry,
    String infraRetryCount,
    String parallelWorkers
) {
    def allureArg = runAllure ? "--alluredir=${env.ALLURE_DIR}" : ''
    def parts = []

    parts << '-vv'
    parts << '-ra'
    parts << '--tb=short'
    parts << '--color=no'
    parts << '-o'
    parts << 'console_output_style=progress'

    def workers = (parallelWorkers ?: '1').trim().toLowerCase()
    if (workers != '1') {
        echo "WARNING: Parallel workers > 1 may break session-scoped extension login; use with caution."
        parts << '-n'
        parts << workers
    }

    if (allureArg) {
        parts << allureArg
    }

    if (enableInfraRetry) {
        def retries = 0
        try {
            retries = Math.max((infraRetryCount ?: '0').trim() as int, 0)
        } catch (Exception ignored) {
            retries = 1
        }

        if (retries > 0) {
            parts << "--reruns=${retries}"
            parts << '--reruns-delay=2'
            parts << '--only-rerun=(selenium\\.common\\.exceptions\\.)?TimeoutException'
            parts << '--only-rerun=(selenium\\.common\\.exceptions\\.)?NoSuchElementException'
            parts << '--only-rerun=(selenium\\.common\\.exceptions\\.)?StaleElementReferenceException'
            parts << '--only-rerun=(selenium\\.common\\.exceptions\\.)?ElementClickInterceptedException'
            parts << '--only-rerun=(selenium\\.common\\.exceptions\\.)?WebDriverException'
            parts << '--only-rerun=SessionNotCreatedException'
            parts << '--only-rerun=urllib3\\.exceptions\\.ReadTimeoutError'
            parts << '--only-rerun=ReadTimeoutError'
            parts << '--only-rerun=HTTPConnectionPool\\(host='
            parts << '--only-rerun=Read\\s+timed\\s+out'
            parts << '--only-rerun=TimeoutError'
            parts << '--only-rerun=timed\\s+out'
            parts << '--only-rerun=disconnected:\\s+not\\s+connected\\s+to\\s+DevTools'
            parts << '--only-rerun=chrome\\s+not\\s+reachable'
            parts << '--only-rerun=ERR_CONNECTION_RESET'
        }
    }

    parts << "--junitxml=${env.PYTEST_JUNIT}"
    parts << "--html=${env.PYTEST_HTML}"
    parts << '--self-contained-html'
    parts << '--json-report'
    parts << "--json-report-file=${env.PYTEST_JSON}"
    if (selectedTestFiles && !selectedTestFiles.isEmpty()) {
        parts.addAll(selectedTestFiles)
    }

    return shellQuotePytestArgs(parts)
}

def resolveSelectedTestFiles(String selectionMode, def paramsObj) {
    def allFiles = getAvailableTestCaseFiles()
    def smokeFiles = getSmokeTestCaseFiles()
    def mode = (selectionMode ?: 'ALL_TESTS').trim().toUpperCase()
    def checkboxMap = getTestCaseCheckboxMap()
    def resolved = checkboxMap
        .findAll { row -> (paramsObj."${row.param}" as boolean) }
        .collect { row -> row.file }
        .unique()
        .sort()

    if (mode == 'ALL_TESTS') {
        if (!resolved.isEmpty()) {
            echo "Checkboxes detected (${resolved.size()}) but TEST_SELECTION_MODE=ALL_TESTS; ignoring checkboxes and running full suite."
        }
        return allFiles
    }

    if (mode == 'SMOKE') {
        if (!resolved.isEmpty()) {
            echo "Checkboxes detected (${resolved.size()}) but TEST_SELECTION_MODE=SMOKE; ignoring checkboxes and running predefined SMOKE suite."
        }
        return smokeFiles
    }

    if (mode != 'CHECKBOX_SELECTION') {
        error("Unsupported TEST_SELECTION_MODE='${selectionMode}'. Allowed values: ALL_TESTS, SMOKE, CHECKBOX_SELECTION.")
    }

    if (resolved.isEmpty()) {
        error('No test checkbox selected. Either select one or more TEST_* checkboxes, or set TEST_SELECTION_MODE=ALL_TESTS.')
    }
    return resolved
}

def validateRuntimeParameters(String selectionMode, String infraRetryCount, String parallelWorkers) {
    def mode = (selectionMode ?: '').trim().toUpperCase()
    if (!(mode in ['ALL_TESTS', 'SMOKE', 'CHECKBOX_SELECTION'])) {
        error("Invalid TEST_SELECTION_MODE='${selectionMode}'. Allowed values: ALL_TESTS, SMOKE, CHECKBOX_SELECTION.")
    }

    def rawRetry = (infraRetryCount ?: '').trim()
    if (!(rawRetry ==~ /^\d+$/)) {
        error("INFRA_RETRY_COUNT must be a non-negative integer, but got '${infraRetryCount}'.")
    }

    def workers = (parallelWorkers ?: '').trim().toLowerCase()
    if (workers == 'auto') {
        return
    }
    if (!(workers ==~ /^\d+$/)) {
        error("PARALLEL_WORKERS must be a non-negative integer or 'auto', but got '${parallelWorkers}'.")
    }
    if ((workers as int) < 1) {
        error("PARALLEL_WORKERS must be >= 1, but got '${parallelWorkers}'.")
    }
}

def getSmokeTestCaseFiles() {
    return [
        'tests/test_dakota_search_time.py',
        'tests/test_dakota_login.py'
    ]
}

def getAvailableTestCaseFiles() {
    return [
        'tests/test_dakota_search_time.py',
        'tests/test_company_detail_loading_time.py',
        'tests/test_company_contacts_loading_time.py',
        'tests/test_company_type_specific_tab_loading_time.py',
        'tests/test_search_load_more_time.py'
    ]
}

def getTestCaseCheckboxMap() {
    return [
        [param: 'TEST_SEARCH_TIME', file: 'tests/test_dakota_search_time.py'],
        [param: 'TEST_DETAIL_LOADING', file: 'tests/test_company_detail_loading_time.py'],
        [param: 'TEST_CONTACTS_LOADING', file: 'tests/test_company_contacts_loading_time.py'],
        [param: 'TEST_TAB_LOADING', file: 'tests/test_company_type_specific_tab_loading_time.py'],
        [param: 'TEST_LOAD_MORE', file: 'tests/test_search_load_more_time.py'],
        [param: 'TEST_LOGIN', file: 'tests/test_dakota_login.py']
    ]
}

def runShell(String unixCommand, String windowsCommand) {
    if (isUnix()) {
        sh(unixCommand)
    } else {
        bat(windowsCommand)
    }
}

def runPytest(String args) {
    runShell(
        """
            ${env.VENV_DIR}/bin/python -m pytest ${args}
        """,
        """
            %VENV_DIR%\\Scripts\\python -m pytest ${args}
        """
    )
}

def getTestStatistics() {
    def stats = [total: 0, passed: 0, failed: 0, skipped: 0]
    def junitPath = env.PYTEST_JUNIT ?: 'test-results/pytest.xml'
    def jsonSnapshot = getFinalOutcomesFromPytestJson()

    if (jsonSnapshot.hasData as boolean) {
        return jsonSnapshot.stats as Map
    }

    if (fileExists(junitPath)) {
        try {
            def xmlText = readFile(junitPath)
            def tests = extractIntFromXmlAttribute(xmlText, 'tests')
            def failures = extractIntFromXmlAttribute(xmlText, 'failures')
            def errors = extractIntFromXmlAttribute(xmlText, 'errors')
            def skipped = extractIntFromXmlAttribute(xmlText, 'skipped')
            def passed = Math.max(tests - failures - errors - skipped, 0)

            stats.total = tests
            stats.failed = failures + errors
            stats.skipped = skipped
            stats.passed = passed
            echo "Using JUnit fallback stats -> total:${stats.total}, passed:${stats.passed}, failed:${stats.failed}, skipped:${stats.skipped}"
        } catch (Exception ex) {
            echo "Could not parse JUnit XML fallback: ${ex.message}"
        }
    } else {
        echo "JUnit XML report not found at ${junitPath}; no fallback stats available."
    }

    return stats
}

def getFailedTestNames() {
    def jsonSnapshot = getFinalOutcomesFromPytestJson()
    if (jsonSnapshot.hasData as boolean) {
        return (jsonSnapshot.failedTests ?: []) as List
    }

    def failures = []
    def junitPath = env.PYTEST_JUNIT ?: 'test-results/pytest.xml'
    if (!fileExists(junitPath)) {
        return failures
    }

    try {
        def xmlText = readFile(junitPath)
        def matcher = (xmlText =~ /(?si)<testcase\b([^>]*)>(?:(?!<\/testcase>).)*<(failure|error)\b/)
        while (matcher.find()) {
            def attrs = matcher.group(1) ?: ''
            def nameMatcher = (attrs =~ /\bname=(["'])(.*?)\1/)
            def classMatcher = (attrs =~ /\bclassname=(["'])(.*?)\1/)
            def name = nameMatcher.find() ? nameMatcher.group(2)?.trim() : ''
            def className = classMatcher.find() ? classMatcher.group(2)?.trim() : ''

            def candidate = name
            if ((!candidate || !candidate.startsWith('test_')) && className) {
                candidate = className.tokenize('.').last()
            }

            if (candidate) {
                failures << candidate
            }
        }
    } catch (Exception ex) {
        echo "Could not parse failed test names from JUnit XML: ${ex.message}"
    }

    return failures.unique()
}

def getSkippedInfraTestNames() {
    def skipped = []
    def junitPath = env.PYTEST_JUNIT ?: 'test-results/pytest.xml'
    if (fileExists(junitPath)) {
        try {
            def xmlText = readFile(junitPath)
            def matcher = (xmlText =~ /(?si)<testcase\b([^>]*)>(?:(?!<\/testcase>).)*<skipped\b[^>]*message=(["'])(.*?)\2/)
            while (matcher.find()) {
                def message = (matcher.group(3) ?: '').trim()
                if (!message.contains('INFRA_SKIP:')) {
                    continue
                }
                def attrs = matcher.group(1) ?: ''
                def nameMatcher = (attrs =~ /\bname=(["'])(.*?)\1/)
                def name = nameMatcher.find() ? nameMatcher.group(2)?.trim() : ''
                if (name) {
                    skipped << name
                }
            }
        } catch (Exception ex) {
            echo "Could not parse infra-skipped test names from JUnit XML: ${ex.message}"
        }
    }
    return skipped.unique()
}

def getFinalOutcomesFromPytestJson() {
    def reportPath = env.PYTEST_JSON ?: 'test-results/report.json'
    def emptyStats = [total: 0, passed: 0, failed: 0, skipped: 0]
    def result = [hasData: false, stats: emptyStats, failedTests: []]

    if (!fileExists(reportPath)) {
        echo "Pytest JSON report not found at ${reportPath}; trying JUnit fallback."
        return result
    }

    try {
        def jsonText = readFile(reportPath)
        def finalOutcomeByNodeId = [:]

        def testMatcher = (jsonText =~ /"nodeid"\s*:\s*"((?:\\.|[^"\\])*)".*?"outcome"\s*:\s*"((?:\\.|[^"\\])*)"/)
        while (testMatcher.find()) {
            def nodeId = (testMatcher.group(1) ?: '')
                .replaceAll(/\\\//, '/')
                .replaceAll(/\\"/, '"')
                .trim()
            def outcome = (testMatcher.group(2) ?: '').trim().toLowerCase()
            if (!nodeId || !outcome) {
                continue
            }
            if (outcome in ['rerun', 're-run']) {
                continue
            }
            if (outcome == 'error') {
                outcome = 'failed'
            }
            if (outcome in ['xfailed', 'xpassed']) {
                outcome = 'skipped'
            }
            if (!(outcome in ['passed', 'failed', 'skipped'])) {
                continue
            }
            finalOutcomeByNodeId[nodeId] = outcome
        }

        def parseSummaryInt = { String key ->
            def m = (jsonText =~ /"summary"\s*:\s*\{(?s).*?"${java.util.regex.Pattern.quote(key)}"\s*:\s*(\d+)/)
            return m.find() ? (m.group(1) ?: '0') as int : 0
        }
        def collected = parseSummaryInt('collected')

        if (!finalOutcomeByNodeId.isEmpty()) {
            def passed = finalOutcomeByNodeId.findAll { _, status -> status == 'passed' }.size()
            def failed = finalOutcomeByNodeId.findAll { _, status -> status == 'failed' }.size()
            def skipped = finalOutcomeByNodeId.findAll { _, status -> status == 'skipped' }.size()
            def total = passed + failed + skipped
            if (collected > 0 && total > collected) {
                def normFailed = Math.min(failed, collected)
                def remainingAfterFailed = Math.max(collected - normFailed, 0)
                def normSkipped = Math.min(skipped, remainingAfterFailed)
                def normPassed = Math.max(collected - normFailed - normSkipped, 0)
                passed = normPassed
                failed = normFailed
                skipped = normSkipped
                total = collected
            }
            def failedTests = finalOutcomeByNodeId
                .findAll { _, status -> status == 'failed' }
                .collect { nodeId, _ -> extractDisplayNameFromNodeId(nodeId as String) }
                .findAll { it }
                .unique()
            return [
                hasData: true,
                stats: [total: total, passed: passed, failed: failed, skipped: skipped],
                failedTests: failedTests
            ]
        }

        def passed = parseSummaryInt('passed')
        def failed = parseSummaryInt('failed') + parseSummaryInt('error')
        def skipped = parseSummaryInt('skipped') + parseSummaryInt('xfailed') + parseSummaryInt('xpassed')
        def total = passed + failed + skipped
        if (collected > 0 && total > collected) {
            def normFailed = Math.min(failed, collected)
            def remainingAfterFailed = Math.max(collected - normFailed, 0)
            def normSkipped = Math.min(skipped, remainingAfterFailed)
            def normPassed = Math.max(collected - normFailed - normSkipped, 0)
            passed = normPassed
            failed = normFailed
            skipped = normSkipped
            total = collected
        }
        if (total > 0) {
            return [hasData: true, stats: [total: total, passed: passed, failed: failed, skipped: skipped], failedTests: []]
        }
    } catch (Exception ex) {
        echo "Could not parse pytest JSON report: ${ex.message}"
    }

    return result
}

def extractDisplayNameFromNodeId(String nodeId) {
    def value = (nodeId ?: '').trim()
    if (!value) {
        return value
    }

    if (value.contains('::')) {
        value = value.tokenize('::').last()
    } else if (value.contains('/')) {
        value = value.tokenize('/').last()
    } else if (value.contains('\\')) {
        value = value.tokenize('\\').last()
    }
    return value.replaceFirst(/\[.*\]$/, '')
}

def extractIntFromXmlAttribute(String xmlText, String attr) {
    if (!xmlText?.trim()) {
        return 0
    }
    def matcher = (xmlText =~ /${java.util.regex.Pattern.quote(attr)}\s*=\s*["'](\d+)["']/)
    if (matcher.find()) {
        return (matcher.group(1) ?: '0') as int
    }
    return 0
}

def logTestSummaryToConsole(String label = 'Test summary') {
    def stats = getTestStatistics()
    def skippedInfraTests = getSkippedInfraTestNames()
    def infraSkipLine = skippedInfraTests
        ? "Infra skipped tests: ${skippedInfraTests.join(', ')}"
        : 'Infra skipped tests: none'
    echo """
================ ${label} ================
Total  : ${stats.total}
Passed : ${stats.passed}
Failed : ${stats.failed}
Skipped: ${stats.skipped}
${infraSkipLine}
==========================================
""".stripIndent()
}

def sendEmailNotification(String buildStatus, String defaultEmail, String additionalEmails) {
    def stats = getTestStatistics()
    def failedTests = getFailedTestNames()
    def actualStatus = currentBuild.result ?: buildStatus

    if (!(actualStatus in ['FAILURE', 'ABORTED'])) {
        if (stats.total == 0) {
            actualStatus = 'UNSTABLE'
        } else if (stats.failed > 0) {
            actualStatus = 'FAILURE'
        } else {
            actualStatus = 'SUCCESS'
        }
    }

    def recipients = collectRecipientEmails(defaultEmail, additionalEmails)
    if (recipients.isEmpty()) {
        echo 'No email recipients configured; skipping email notification.'
        return
    }

    def jobUrl = env.BUILD_URL ?: ''
    def excelRelPath = prepareExcelArtifactPath()
    def excelExists = excelRelPath ? fileExists(excelRelPath) : false
    def allureUrl = "${jobUrl}allure"
    def pytestHtmlUrl = "${jobUrl}Pytest_20HTML_20Report/"
    def durationString = (currentBuild.durationString ?: 'N/A').replace(' and counting', '')
    def passRate = stats.total > 0 ? ((stats.passed * 100) / stats.total) as int : 0
    def cleanedFailedTests = failedTests.collect { name ->
        def prettyName = normalizeFailedTestNameToLabel(name ?: '')
        prettyName
            .replaceAll(/(?i)exccedded/, 'exceeded')
            .replaceAll(/(?i)\btab\(s\)\b/, 'Tabs')
            .trim()
    }.findAll { it }
    def failedTestSummary = cleanedFailedTests
        ? cleanedFailedTests.collect { item ->
            "<div style=\"margin:0 0 6px;padding:7px 10px;background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;color:#9a3412;\">${item}</div>"
        }.join('')
        : '<span style="color:#065f46;font-weight:600;">No failed tests or tab timeouts were detected in this run.</span>'

    def subject = "Dakota Chrome Extension Performance | ${new Date().format('MMMM d, yyyy')}"

    def body = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Dakota Performance Report</title>
</head>
<body style="margin:0;padding:0;background:linear-gradient(140deg,#e0ecff 0%,#efe7ff 45%,#fff6e5 100%);font-family:'Segoe UI',Roboto,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td align="center" style="padding:24px;">
        <table width="760" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #dbe3ee;box-shadow:0 14px 32px rgba(30,64,175,0.14);">
          <tr>
            <td style="padding:26px 30px;background:linear-gradient(135deg,#0f172a 0%,#1e40af 52%,#7c3aed 100%);color:#ffffff;">
              <h2 style="margin:0;font-size:30px;letter-spacing:0.2px;">Dakota Chrome Extension Performance</h2>
              <p style="margin:8px 0 0;opacity:0.9;font-size:13px;">Selenium headless • Excel timings • Allure report</p>
            </td>
          </tr>

          <tr>
            <td style="padding:24px 30px 10px;">
              <h3 style="margin:0 0 12px;color:#0f172a;font-size:17px;">Build Details</h3>
              <table width="100%" cellpadding="8" cellspacing="8" style="font-size:13px;margin-bottom:12px;">
                <tr align="center">
                  <td style="background:linear-gradient(180deg,#ccfbf1 0%,#99f6e4 100%);color:#134e4a;border-radius:12px;box-shadow:0 6px 14px rgba(20,184,166,0.22);"><div style="font-size:11px;letter-spacing:0.4px;">TOTAL</div><div style="font-size:24px;font-weight:800;">${stats.total}</div></td>
                  <td style="background:linear-gradient(180deg,#dcfce7 0%,#86efac 100%);color:#14532d;border-radius:12px;box-shadow:0 6px 14px rgba(34,197,94,0.25);"><div style="font-size:11px;letter-spacing:0.4px;">PASSED</div><div style="font-size:24px;font-weight:800;">${stats.passed}</div></td>
                  <td style="background:linear-gradient(180deg,#fee2e2 0%,#fca5a5 100%);color:#7f1d1d;border-radius:12px;box-shadow:0 6px 14px rgba(239,68,68,0.22);"><div style="font-size:11px;letter-spacing:0.4px;">FAILED</div><div style="font-size:24px;font-weight:800;">${stats.failed}</div></td>
                  <td style="background:linear-gradient(180deg,#ede9fe 0%,#c4b5fd 100%);color:#4c1d95;border-radius:12px;box-shadow:0 6px 14px rgba(124,58,237,0.22);"><div style="font-size:11px;letter-spacing:0.4px;">SKIPPED</div><div style="font-size:24px;font-weight:800;">${stats.skipped}</div></td>
                </tr>
              </table>
              <table width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;color:#1e293b;border:1px solid #bfdbfe;border-radius:12px;overflow:hidden;background:linear-gradient(180deg,#f8fbff 0%,#ffffff 100%);table-layout:fixed;">
                <tr>
                  <td width="32%" style="padding:10px 12px;background:linear-gradient(180deg,#dbeafe 0%,#bfdbfe 100%);border-bottom:1px solid #bfdbfe;"><strong>Duration</strong></td>
                  <td style="padding:10px 12px;border-bottom:1px solid #dbe3f3;font-weight:600;color:#1e3a8a;">${durationString}</td>
                </tr>
                <tr>
                  <td style="padding:10px 12px;background:linear-gradient(180deg,#dbeafe 0%,#bfdbfe 100%);border-bottom:1px solid #bfdbfe;"><strong>Passed Percentage</strong></td>
                  <td style="padding:10px 12px;border-bottom:1px solid #dbe3f3;color:#0f766e;font-weight:700;">${passRate}%</td>
                </tr>
                <tr>
                  <td style="padding:10px 12px;background:linear-gradient(180deg,#dbeafe 0%,#bfdbfe 100%);"><strong>Failed Tests / Affected Tabs</strong></td>
                  <td style="padding:10px 12px;line-height:1.45;">${failedTestSummary}</td>
                </tr>
              </table>
            </td>
          </tr>

          <tr>
            <td style="padding:8px 30px 24px;">
              <h3 style="margin:0 0 12px;color:#0f172a;font-size:17px;">Report Access</h3>
              <table width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;color:#1e293b;border:1px solid #c4b5fd;border-radius:10px;overflow:hidden;background:linear-gradient(180deg,#faf5ff 0%,#f3f0ff 100%);">
                <tr>
                  <td width="32%" style="padding:10px 12px;background:linear-gradient(180deg,#ede9fe 0%,#ddd6fe 100%);border-bottom:1px solid #e9d5ff;"><strong>Jenkins Build</strong></td>
                  <td style="padding:10px 12px;border-bottom:1px solid #e9d5ff;">
                    <a style="color:#6d28d9;text-decoration:underline;font-weight:700;" href="${jobUrl}">Open Build #${env.BUILD_NUMBER ?: ''}</a>
                  </td>
                </tr>
                <tr>
                  <td width="32%" style="padding:10px 12px;background:linear-gradient(180deg,#ede9fe 0%,#ddd6fe 100%);border-bottom:1px solid #e9d5ff;"><strong>Allure Report</strong></td>
                  <td style="padding:10px 12px;border-bottom:1px solid #e9d5ff;">
                    <a style="color:#6d28d9;text-decoration:underline;font-weight:700;" href="${allureUrl}">Open Allure Report</a>
                  </td>
                </tr>
                <tr>
                  <td width="32%" style="padding:10px 12px;background:linear-gradient(180deg,#ede9fe 0%,#ddd6fe 100%);"><strong>Pytest HTML</strong></td>
                  <td style="padding:10px 12px;">
                    <a style="color:#6d28d9;text-decoration:underline;font-weight:700;" href="${pytestHtmlUrl}">Open Pytest HTML Report</a>
                  </td>
                </tr>
              </table>
              <p style="margin:12px 0 0;color:#64748b;font-size:12px;">Excel file <strong>dakota_chrome_extension_results.xlsx</strong> is attached to this email when the performance suite runs.</p>
            </td>
          </tr>

          <tr>
            <td style="padding:13px 30px;background:#0f172a;color:#cbd5e1;font-size:12px;">
              Jenkins CI/CD • Dakota Chrome Extension Performance • http://110.93.205.18:8080/
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    def baseArgs = [
        subject: subject,
        body: body,
        mimeType: 'text/html',
        attachLog: false,
        compressLog: false
    ]
    if (excelExists) {
        baseArgs.attachmentsPattern = excelRelPath
    }

    def recipientList = recipients.join(', ')
    echo "Sending email to: ${recipientList}"

    try {
        emailext(baseArgs + [to: recipientList])
    } catch (Exception ex) {
        echo "Combined email send failed: ${ex.getMessage()}"
        echo 'Falling back to one-by-one recipient delivery.'
        recipients.each { recipient ->
            try {
                echo "Sending fallback email to: ${recipient}"
                emailext(baseArgs + [to: recipient])
            } catch (Exception innerEx) {
                echo "Failed to send email to ${recipient}: ${innerEx.getMessage()}"
            }
        }
    }
}

def normalizeFailedTestNameToLabel(String testName) {
    def value = (testName ?: '').trim()
    if (!value) {
        return value
    }

    value = value
        .replaceFirst(/^.*::/, '')
        .replaceFirst(/^.*[\\\/]/, '')
        .replaceFirst(/\.py$/, '')
    if (value.contains('.') && value.tokenize('.').last().startsWith('test_')) {
        value = value.tokenize('.').last()
    }

    def labelMap = [
        'test_dakota_search_time'                      : 'Company Search Time',
        'test_company_detail_loading_time'             : 'Company Detail Loading Time',
        'test_company_contacts_loading_time'           : 'Company Contacts Loading Time',
        'test_company_type_specific_tab_loading_time'  : 'Company Type Tab Loading Time',
        'test_search_load_more_time'                   : 'Search Load More Time',
        'test_dakota_portal_and_extension_login'       : 'Portal And Extension Login',
        'test_dakota_login_step_by_step'               : 'Extension Login Step By Step'
    ]
    if (labelMap.containsKey(value)) {
        return labelMap[value]
    }

    value = value
        .replaceFirst(/^test_/, '')
        .replaceFirst(/_loading_time$/, '')
        .replaceFirst(/_time$/, '')
        .replaceFirst(/\[.*\]$/, '')

    def words = value
        .split(/_+/)
        .findAll { it?.trim() }
        .collect { it.toLowerCase().capitalize() }

    return words ? words.join(' ') : testName
}

def prepareExcelArtifactPath() {
    def excelPath = env.EXCEL_REPORT ?: 'reports/dakota_chrome_extension_results.xlsx'
    if (fileExists(excelPath)) {
        return excelPath
    }
    echo "Excel artifact not found at expected path: ${excelPath}"
    return null
}

def collectRecipientEmails(String defaultEmail, String additionalEmails) {
    def recipients = []
    def seen = [] as Set

    [defaultEmail, additionalEmails].findAll { it?.trim() }.each { source ->
        source
            .split(/[,\s;]+/)
            .collect { it.trim() }
            .findAll { it }
            .each { mail ->
                def normalized = mail.toLowerCase()
                if (!seen.contains(normalized)) {
                    seen.add(normalized)
                    recipients.add(mail)
                }
            }
    }

    echo "Email recipients resolved: ${recipients.join(', ')}"
    return recipients
}
