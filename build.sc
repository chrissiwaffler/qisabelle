import mill._, scalalib._

// We put build.sc and hence ServerDockerfile in the root directory of the project,
// otherwise VSCode doesn't find it.

object server extends ScalaModule {
  def scalaVersion = "2.13.14"

  def scalacOptions: T[Seq[String]] = Seq("-deprecation", "-Xfatal-warnings")

  def ivyDeps = Agg(
    ivy"com.lihaoyi::os-lib:0.10.2",
    ivy"com.lihaoyi::cask:0.9.2",
    // ivy"com.lihaoyi::scalatags:0.13.1",
    // ivy"de.unruh::scala-isabelle::v0.4.2",
    ivy"de.unruh::scala-isabelle:master-SNAPSHOT",
    // resolvers ++= Resolver.sonatypeOssRepos("snapshots"),
  )

  object test extends ScalaTests {
    def testFramework = "org.scalatest.tools.Framework"
    def ivyDeps = Agg(
      ivy"org.scalatest::scalatest:3.2.18",
      ivy"com.lihaoyi::requests::0.8.3"
    )
  }
}
