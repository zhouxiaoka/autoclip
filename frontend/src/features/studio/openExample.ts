import { exampleProjectApi } from '../../services/api'
import { beginExperience } from '../../analytics/experience'
import { workflow } from '../../analytics/observer'

/** The home-page sample project. DiagnosePanel uses the same path. */
export async function openExample(navigate: (to: string) => void): Promise<void> {
  const finish = beginExperience('example_project_open', { material_origin: 'sample' })
  try {
    const { project_id, resolution, example_version } = await exampleProjectApi.create()
    workflow.rememberProject(project_id, { material_origin: 'sample', example_version })
    finish('completed', { resolution, example_version, ...workflow.context(project_id) })
    navigate(`/project/${project_id}`)
  } catch (error) {
    finish('failed', {}, error)
    throw error
  }
}
