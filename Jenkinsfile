pipeline {

  agent {
    label 'docker'
  }

  options {
    timeout(time: 1, unit: 'HOURS')
    skipDefaultCheckout(true)
  }

  stages {

    stage('Checkout') {
      steps {
        deleteDir()
        script {
          try {
            scmVars = checkout(scm)
          } catch (e) {
            echo 'Got exception, sleep 15s...'
            sleep(15)
            throw e
          }
          for (var in scmVars) {
            echo "Add ENV['${var.key}']='${var.value}'"
            env[var.key] = var.value
          }
        }
      }
      options {
        retry(5)
      }
    }

    stage("Init") {
      steps {
        sh 'make init'
        script {
          def version = readFile('version.txt').trim()
          def timestamp = new Date().format('yyyyMMddHHmmss')
          currentBuild.displayName = "#${currentBuild.number}: ${version} [${timestamp}]"
        }
      }
    }

    stage('Build') {
      steps {
        sh 'make image'
        script {
          if (fileExists("test-output/test.out")) {
            currentBuild.result = "UNSTABLE"
            emailBodyTestsOutput = sh(
              returnStdout: true,
              script: "cat test-output/test.out | ansi2html -n -w"
            )
          }
        }
      }
      options {
        ansiColor('vga')
      }
    }

    stage('Push') {
      steps {
        sh 'make push'
      }
    }

  }

  post {

    always {
      script {
        emailBody = '<html>\n<body>\n<h3>$PROJECT_NAME - Build # $BUILD_NUMBER - $BUILD_STATUS</h3>\n\n'
        if (env.GIT_PREVIOUS_SUCCESSFUL_COMMIT) {
          emailBody += '<h4>Changelog:</h4>\n'
          emailBody += sh(
            returnStdout: true,
            script: "git log --color --pretty='tformat:%C(yellow)%h %Cblue%s %Creset// %an <%ae>' ${env.GIT_PREVIOUS_SUCCESSFUL_COMMIT}..HEAD | ansi2html -n -w"
          )
          emailBody += '\n'
        }
        emailBody += '<p>Check details at <a href="$BUILD_URL">$BUILD_URL</a></p>\n\n'
      }
    }

    fixed {
      script {
        notifyResult = 'RECOVERY'
      }
    }

    unstable {
      script {
        notifyResult = 'UNSTABLE'
        emailBody += '<h4>Tests Output:</h4>\n'
        emailBody += emailBodyTestsOutput
      }
    }

    failure {
      script {
        notifyResult = 'FAILURE'
        emailBody += '<h4>Console output:</h4>\n<pre>${BUILD_LOG, maxLines=9999, escapeHtml=true}</pre>\n'
      }
    }

    cleanup {
      script {
        try { notifyResult = notifyResult } catch(ex) { notifyResult = 'SUCCESS' }
        emailBody += '</body>\n</html>\n'
      }
      emailext(
        to: env.MAILTO,
        subject: "${notifyResult}: Job '${env.JOB_NAME} [${currentBuild.displayName}]'",
        mimeType: 'text/html',
        body: emailBody,
      )
    }

  }

}
// vim: set filetype=Jenkinsfile tabstop=2 softtabstop=2 shiftwidth=2 expandtab:
