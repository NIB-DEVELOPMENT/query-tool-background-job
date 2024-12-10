def remote = [:]
remote.name = 'devadmin'
remote.host = '192.168.100.123'
remote.allowAnyHosts = true


pipeline {
    agent any
    environment {
        DEV_CREDS = credentials('devadmin')
        DOCKER_CREDS = credentials('DockerHub')
    }
    stages {
        stage('Rebuild Background Image'){
            steps {
                    sh 'docker build -t nibitdev/query-tool-backend:delay .'
                }
            }
        stage('Login to DockerHub'){
            steps {
                sh 'echo $DOCKER_CREDS_PSW | docker login -u $DOCKER_CREDS_USR --password-stdin'
            }
        }
        stage('Push Background Job Image'){
            steps {
                sh 'docker push nibitdev/query-tool-backend:delay'
            }
        }
        }
        post {
            always {
                sh 'docker logout'
            }
        }
    }